# Copyright 2016 ETH Zurich
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# External packages
from django.conf import settings
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django_webtest import WebTest
from guardian.shortcuts import assign_perm

# SCION-WEB
from ad_manager.models import ISD, AD


class BasicWebTest(WebTest):

    fixtures = ['ad_manager/tests/test_topology.json']

    def setUp(self):
        super().setUp()
        self.isds = {}
        for isd in ISD.objects.all():
            self.isds[isd.id] = isd

        self.ads = {}
        for ad in AD.objects.all():
            self.ads[ad.as_id] = ad

    def _get_ad_detail(self, ad, *args, **kwargs):
        if isinstance(ad, AD):
            ad = ad.as_id
        assert isinstance(ad, int)
        return self.app.get(reverse('ad_detail', args=[ad]), *args, **kwargs)

    def _find_form_by_action(self, response, view_name, *args, **kwargs):
        if args is None:
            args = []
        url = reverse(view_name, *args, **kwargs)
        all_forms = response.forms.values()
        form = next(filter(lambda f: f.action == url, all_forms))
        return form


class BasicWebTestUsers(BasicWebTest):

    def setUp(self):
        super().setUp()
        assert not settings.ENABLED_2FA
        self._create_users()

    def _create_users(self):
        self.admin_user = User.objects.create_superuser(username='admin',
                                                        password='admin',
                                                        email='')
        self.user = User.objects.create_user(username='user1',
                                             password='user1',
                                             email='')


class TestListIsds(BasicWebTest):

    def test_list_isds(self):
        isd_name = 'ISD 2'
        isd_list = self.app.get(reverse('list_isds'))
        self.assertContains(isd_list, isd_name)

        # Click on the isd link
        isd_detail = isd_list.click(isd_name)
        self.assertContains(isd_detail, isd_name)


class TestListAds(BasicWebTest):

    def test_list_ads(self):
        isd = self.isds[2]
        isd_name = 'ISD 2'
        ad_list = self.app.get(reverse('isd_detail', args=[isd.id]))
        self.assertContains(ad_list, isd_name)
        self.assertNotContains(ad_list, str(self.ads[1]))

        for ad_id in [21, 22, 23]:
            ad = self.ads[ad_id]
            self.assertContains(ad_list, str(ad))

    def test_list_core(self):
        isd = self.isds[2]
        ad = self.ads[21]
        ad.is_core_ad = True
        ad.save()
        assert ad.isd == isd

        ad_list = self.app.get(reverse('isd_detail', args=[isd.id]))
        self.assertContains(ad_list, ad.as_id)
        li_tag = ad_list.html.find('a', text='AS 2-21').parent
        self.assertIn('core', li_tag.text)


class TestAdDetail(BasicWebTest):

    def test_servers_page(self):
        ad = self.ads[1]
        ad_detail = self._get_ad_detail(ad)
        self.assertContains(ad_detail, str(ad))
        html = ad_detail.html
        beacon_servers = html.find(id="beacon-servers-table")
        certificate_servers = html.find(id="certificate-servers-table")
        path_servers = html.find(id="path-servers-table")
        routers = html.find(id="routers-table")

        # Test that tables are not empty
        tables = [beacon_servers, certificate_servers, path_servers, routers]
        for table in tables:
            assert table, 'No table found'
            self.assertFalse('No servers' in str(table), "Table is empty")

        # Test that all beacon servers are listed
        for service in ad.serviceaddress_set.all():
            obj = service.service
            if 'bs' in obj.name:
                assert service.addr in beacon_servers.text

        # Test that routers are listed correctly
        router_rows = routers.find_all('tr')[1:]
        for intf in ad.borderrouterinterface_set.all():
            obj = intf.router_addr.router
            row = next(filter(lambda x: obj.name in x.text, router_rows))
            isd_ad = '{}-{}'.format(intf.neighbor_isd_id, intf.neighbor_as_id)
            assert isd_ad in row.text
            assert intf.addr in row.text
            assert intf.remote_addr in row.text
            assert intf.neighbor_type in row.text

    def test_labels(self):
        ad = self.ads[1]
        value_map = {True: 'Yes', False: 'No'}

        # Test core label
        for is_core_value, page_value in value_map.items():
            ad.is_core_ad = is_core_value
            ad.save()
            ad_detail = self._get_ad_detail(ad)
            core_container = ad_detail.html.find(id='core-label')
            self.assertIn(page_value, core_container.text,
                          'Invalid label: core')


class TestUsersAndPermissions(BasicWebTestUsers):

    CONTROL_CLASS = 'process-control-form'

    def test_login_admin(self):
        ad_detail = self._get_ad_detail(self.ads[1])
        self.assertNotContains(ad_detail, 'admin')
        login_page = ad_detail.click('Login')
        login_form = login_page.form
        login_form['username'] = 'admin'
        login_form['password'] = 'admin'
        res = login_form.submit().follow()
        self.assertContains(res, 'AS 1')
        self.assertContains(res, 'Logged in as:')
        self.assertContains(res, 'admin')

    def test_admin_panel(self):
        admin_index = reverse('admin:index')
        # Anon user
        login_page = self.app.get(admin_index).follow()
        self.assertContains(login_page, 'Username:')

        # Non-admin user
        admin_page = self.app.get(admin_index, user=self.user)
        self.assertContains(admin_page, 'Site administration')
        self.assertContains(admin_page, "You don't have permission")

        # Admin user
        admin_page = self.app.get(admin_index, user=self.admin_user)
        self.assertContains(admin_page, 'Site administration')
        self.assertContains(admin_page, 'Authentication and Authorization')

    def test_login_logout(self):
        home = self.app.get('/', user=self.user).maybe_follow()
        res = home.click('logout').maybe_follow()
        self.assertContains(res, 'Login')


class TestConnectionRequests(BasicWebTestUsers):

    def _get_request_page(self, ad_id):
        requests_page = reverse('ad_connection_requests', args=[ad_id])
        return requests_page

    def test_view_nopriv(self):
        ad = self.ads[2]
        requests_page = self._get_request_page(ad.as_id)

        # Anon user
        ad_requests = self.app.get(requests_page)
        self.assertNotContains(ad_requests, 'Received requests')
        self.assertNotContains(ad_requests, 'Created by')

        # Non-priv user
        ad_requests = self.app.get(requests_page, user=self.user)
        self.assertNotContains(ad_requests, 'Received requests')
        self.assertNotContains(ad_requests, 'Created by')

    def test_priv_user(self):
        ad = self.ads[2]
        requests_page = self._get_request_page(ad.as_id)

        # Admin user
        ad_requests = self.app.get(requests_page, user=self.admin_user)

        self.assertContains(ad_requests, 'Received connection requests')

        # User which has access to the AD
        assign_perm('change_ad', self.user, ad)
        ad_requests = self.app.get(requests_page, user=self.user)
        self.assertContains(ad_requests, 'Received connection requests')
