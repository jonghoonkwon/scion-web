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
from django.conf.urls import patterns, url

# SCION-WEB
from ad_manager import views

api_patterns_internal = patterns(
    '',
    url(r'^api/v1/internal/isd/(?P<isd_id>\d+)/as/(?P<as_id>\d+)/topo_hash/?$',
        views.as_topo_hash, name='topo_hash'),
    url(r'^api/v1/internal/update_coord_settings/?$',
        views.coord_service_update, name='coord_service_update'),
    url(r'^api/v1/internal/join_requests/isd-as/(?P<isd_as>\d+-\d+)'
        '/request/(?P<request_id>\d+)/?$',
        views.join_request_action, name='join_request_action'),
    url(r'^api/v1/internal/.*$',
        views.wrong_api_call, name='wrong_api_call'),
)

api_patterns_external = patterns(
    # unimplemented API calls get treated as wrong API calls
    '',
    url(r'^api/v1/services_status/?$',
        views.wrong_api_call, name='services_status'),
    url(r'^api/v1/open_policy/?$',
        views.wrong_api_call, name='open_policy'),
    url(r'^api/v1/receive_notification/?$',
        views.wrong_api_call, name='receive_notification'),
    url(r'^api/v1/peering_request/?$',
        views.wrong_api_call, name='peering_request'),
    url(r'^api/v1/.*$',
        views.wrong_api_call, name='wrong_api_call'),  # Default route
)

isd_patterns = patterns(
    '',
    url(r'^isds/?$',
        views.ISDListView.as_view(), name='list_isds'),
    url(r'^isds/upload_file/?$',
        views.upload_file, name='upload_file_ref'),
    url(r'^isds/add_isd/?$',
        views.add_isd, name='add_isd'),
    url(r'^isds/join_isd/?$',
        views.request_join_isd, name='join_isd'),
    url(r'^isds/poll_join_reply/?$',
        views.poll_join_reply, name='poll_join_reply'),
    url(r'^isds/save_all_topologies/?$',
        views.save_all_topologies, name='save_all_topologies'),
    url(r'^isds/(?P<pk>\d+)/?$',
        views.ISDDetailView.as_view(), name='isd_detail'),
)

ad_patterns = patterns(
    '',
    url(r'^ads/(?P<as_id>\d+)/?$',
        views.ADDetailView.as_view(), name='ad_detail'),
    url(r'^ads/(?P<as_id>\d+)/#!topology/?$',
        views.ADDetailView.as_view(), name='ad_detail_topology'),
    url(r'^ads/(?P<as_id>\d+)/#!topology&expanded_routers/?$',
        views.ADDetailView.as_view(), name='ad_detail_topology_routers'),
    url(r'^ads/(?P<as_id>\d+)/#!updates/?$',
        views.ADDetailView.as_view(), name='ad_detail_updates'),
    url(r'^ads/(?P<as_id>\d+)/#!requests/?$',
        views.ADDetailView.as_view(), name='ad_connection_requests'),
    url(r'^ads/generate_topology/?$',
        views.generate_topology, name='generate_topology'),
    url(r'^ads/add_to_topology/?$',
        views.add_to_topology, name='add_to_topology'),
    url(r'^ads/isd/(?P<isd_id>\d+)/as/(?P<as_id>\d+)/simple_configuration/?$',
        views.simple_configuration, name='simple_configuration'),
)

connection_request_patterns = patterns(
    '',
    url(r'^connection_requests/new/(?P<as_id>\d+)/?$',
        views.ConnectionRequestView.as_view(), name='new_connection_request'),
    url(r'^connection_requests/(?P<con_req_id>\d+)/action/?$',
        views.connection_request_action, name='connection_request_action'),
)

misc = patterns(
    '',
    url(r'^network/?$',
        views.network_view, name='network_view'),
    url(r'^network/isd/(?P<isd_id>\d+)/as/(?P<as_id>\d+)/?$',
        views.network_view_neighbors, name='network_view_as'),
    url(r'^coord_service/?$',
        views.coord_service, name='coord_service'),
)

urlpatterns = api_patterns_internal + isd_patterns + ad_patterns + \
              connection_request_patterns + misc
