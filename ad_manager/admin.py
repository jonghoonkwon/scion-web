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
from django.contrib import admin
from django.contrib.admin import AdminSite
from django.contrib.auth import get_permission_codename
from django.contrib.auth.models import User, Group
from django.core.urlresolvers import reverse
from guardian.admin import GuardedModelAdmin

# SCION
from two_factor.admin import AdminSiteOTPRequiredMixin
from two_factor.models import PhoneDevice

# SCION-WEB
from ad_manager.models import (
    AD,
    BeaconServerWeb,
    CertificateServerWeb,
    ConnectionRequest,
    ISD,
    OrganisationAdmin,
    PathServerWeb,
    RouterWeb,
)


class MyAdminSite(AdminSite):
    def has_permission(self, request):
        """
        Every registered active user is allowed to view *at least* one page of
        the admin website.
        """
        return request.user.is_active


class MyAdminOTPSite(AdminSiteOTPRequiredMixin, MyAdminSite):
    pass


if settings.ENABLED_2FA:
    admin_site = MyAdminOTPSite(name='2fa_admin')
else:
    admin_site = MyAdminSite(name='basic_admin')
admin_site.register(User)
admin_site.register(Group)


class PrivilegedChangeAdmin(GuardedModelAdmin):
    list_select_related = True

    def has_change_permission(self, request, obj=None):
        opts = self.opts
        codename = get_permission_codename('change', opts)

        # If there is an 'ad' attribute then it's a foreign key, so extend
        # user permissions for this AS to the current object
        ad = getattr(obj, 'ad', None)
        if ad and isinstance(ad, AD):
            obj = ad
            codename = 'change_ad'
        return request.user.has_perm("%s.%s" % (opts.app_label, codename), obj)

    def get_readonly_fields(self, request, obj=None):
        """
        Make fields listed in 'privileged fields' read-only
        """
        fields = super().get_readonly_fields(request, obj)
        if not request.user.has_perm('change_ad'):
            fields += self.privileged_fields
        return fields

    def get_queryset(self, request):
        # Add ordering
        return super().get_queryset(request).order_by('id')


@admin.register(AD, ISD, OrganisationAdmin, site=admin_site)
class SortRelatedAdmin(PrivilegedChangeAdmin):
    privileged_fields = ('isd', 'is_core_ad',)


@admin.register(BeaconServerWeb,
                CertificateServerWeb,
                PathServerWeb,
                site=admin_site)
class ServerAdmin(PrivilegedChangeAdmin):
    fields = ('name', 'addr', ('ad', 'ad_link'),)
    privileged_fields = ('ad',)
    readonly_fields = ('ad_link',)
    raw_id_fields = ('ad',)

    def ad_link(self, obj):
        link = reverse('admin:{}_ad_change'.format(self.opts.app_label),
                       args=[obj.ad.id])
        return '<a href="{}">Edit AD</a>'.format(link)
    ad_link.allow_tags = True
    # FIXME hack. How to remove this completely?
    ad_link.short_description = ':'


@admin.register(RouterWeb, site=admin_site)
class RouterAdmin(ServerAdmin):
    list_display = ('ad', 'addr', 'neighbor_isd_id', 'neighbor_as_id',
                    'neighbor_type', 'interface_addr', 'interface_toaddr')

    def get_fields(self, request, obj=None):
        # FIXME is there a way to make it more explicit?
        self.raw_id_fields += ('neighbor_isd_id', 'neighbor_as_id')
        fields = super().get_fields(request, obj)
        fields += ('interface_id',
                   ('interface_addr', 'interface_port'),
                   ('interface_toaddr', 'interface_toport'),
                   ('neighbor_isd_id', 'neighbor_as_id', 'neighbor_type'))
        return fields


# Misc admin models
admin_site.register(ConnectionRequest)
admin_site.register(PhoneDevice)
