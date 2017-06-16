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

# Stdlib
import copy
import glob
import json
import os
import re
import shutil
import tempfile
from ipaddress import ip_address

# SCION
from ad_manager.models import (
    AD,
    BorderRouterAddress,
    BorderRouterInterface,
    ServiceAddress,
)
from ad_manager.util.common import is_private_address

from lib.crypto.trc import get_trc_file_path
from lib.defines import PROJECT_ROOT
from lib.types import LinkType
from lib.util import read_file, write_file
from topology.generator import (
    ConfigGenerator,
    DEFAULT_PATH_POLICY_FILE,
    DEFAULT_ZK_CONFIG,
)


# values to be used for generating test data
IP_ADDRESS_BASE = '127.0.0.1'
TEST_UDP_PORT = 50000
TEST_PORT = 31041
GEN_PATH = os.path.join(PROJECT_ROOT, 'gen')


# test connection types
CORE_CONNECTION = 'CORE_CORE'
PARENT_CHILD_CONNECTION = 'PARENT_CHILD'  # First AS is parent of the second
PEER_CONNECTION = 'PEER_PEER'


def find_last_router(topo_dict):
    """
    Return a tuple: (index, router_dict)
    """
    assert 'BorderRouters' in topo_dict
    routers = topo_dict['BorderRouters']
    if routers:
        sorted_routers = sorted(routers.items(),
                                key=lambda pair: ip_address(pair[1]['Addr']))
        return sorted_routers[-1]
    else:
        return None


def find_next_ip_local():
    max_ip = ip_address(IP_ADDRESS_BASE)
    topo_files = glob.glob(os.path.join(
        GEN_PATH, 'ISD*', 'topologies', 'ISD*.json'))

    ip_addr_re = re.compile(r'"((\d{1,3}\.){3}\d{1,3})"')
    # Scan all config files for IP addresses, select the largest
    for path in topo_files:
        contents = open(path).read()
        for match in re.finditer(ip_addr_re, contents):
            ip_addr = ip_address(match.group(1))
            if ip_addr > max_ip:
                max_ip = ip_addr
    return str(max_ip + 1)


def find_next_ip_global():
    max_ip = ip_address(IP_ADDRESS_BASE)

    # Routers
    object_groups = [BorderRouterAddress.objects.all(),
                     BorderRouterInterface.objects.all()]
    for group in object_groups:
        for element in group:
            element_addr = ip_address(element.addr)
            if element_addr > max_ip and is_private_address(element_addr):
                max_ip = element_addr

    # Services
    for service in ServiceAddress.objects.all():
        addr = ip_address(service.addr)
        if addr > max_ip and is_private_address(addr):
            max_ip = addr

    return max_ip + 1


def ip_generator():
    next_ip = find_next_ip_global()
    while True:
        yield str(next_ip)
        next_ip += 1


def create_next_router(topo_dict, ip_gen):
    """
    Creates a test router dictionary with generated IP addresses
    and test values.
    """
    router_item = find_last_router(topo_dict)
    if router_item:
        _, last_router = router_item
        new_router = copy.deepcopy(last_router)
        last_index = sorted(topo_dict['BorderRouters'].keys(),
                            key=lambda x: -int(x))[0]
        router_index = int(last_index) + 1

        nr_addr = next(ip_gen)
        nr_if_addr = next(ip_gen)

        new_router['InternalAddr'][0]['Public'][0]['Addr'] = nr_addr
        new_router['Interfaces'][router_index] = {}
        new_router['Interfaces'][router_index]['Public']['Addr'] = nr_if_addr
        new_router['Interfaces'][router_index]['Remote']['Addr'] = 'NULL'
    else:
        ip_address_loc = next(ip_gen)
        ip_address_pub = next(ip_gen)
        router_index = 1
        if_id = 0
        new_router = {
            'InternalAddrs': [{
                'Public': [{
                    'Addr': str(ip_address_loc),
                    'L4Port': TEST_PORT,
                }]
            }],
            'Interfaces': {
                str(if_id): {
                    'Public': {
                        'Addr': str(ip_address_pub),
                        'L4Port': TEST_UDP_PORT,
                    },
                    'Remote': {
                        'Addr': 'NULL',
                        'L4Port': TEST_UDP_PORT,
                    },
                    'InternalAddrIdx': 0,
                    'Bandwidth': 1000,
                    'MTU': 1472,
                }
            }
        }
    return str(if_id), str(router_index), new_router


def link_topologies(first_topo, second_topo, connection_type):
    first_topo = copy.deepcopy(first_topo)
    second_topo = copy.deepcopy(second_topo)
    ip_gen = ip_generator()
    first_ifid, first_router_id, first_topo_router = create_next_router(first_topo,
                                                                        ip_gen)
    second_ifid, second_router_id, second_topo_router = create_next_router(second_topo,
                                                                           ip_gen)

    first_router_if = first_topo_router['Interfaces'][first_ifid]
    second_router_if = second_topo_router['Interfaces'][second_ifid]

    first_ad_id = first_topo['ADID']
    second_ad_id = second_topo['ADID']

    first_router_if['Remote']['Addr'] = second_router_if['Public']['Addr']
    first_router_if['ISD_AS'] = '{}-{}'.format(second_topo['ISDID'],
                                               second_ad_id)

    second_router_if['Remote']['Addr'] = first_router_if['Public']['Addr']
    second_router_if['ISD_AS'] = '{}-{}'.format(first_topo['ISDID'],
                                                first_ad_id)

    if connection_type == CORE_CONNECTION:
        first_router_if['LinkType'] = LinkType.CORE
        second_router_if['LinkType'] = LinkType.CORE
    elif connection_type == PEER_CONNECTION:
        first_router_if['LinkType'] = LinkType.PEER
        second_router_if['LinkType'] = LinkType.PEER
    elif connection_type == PARENT_CHILD_CONNECTION:
        first_router_if['LinkType'] = LinkType.CHILD
        second_router_if['LinkType'] = LinkType.PARENT
    else:
        raise ValueError('Invalid link type')

    first_topo['BorderRouters'][first_router_id] = first_topo_router
    second_topo['BorderRouters'][second_router_id] = second_topo_router

    return first_topo, second_topo


def link_ads(first_ad, second_ad, connection_type):
    """Needs transaction!"""
    assert isinstance(first_ad, AD)
    assert isinstance(second_ad, AD)
    first_topo = first_ad.generate_topology_dict()
    second_topo = second_ad.generate_topology_dict()
    first_topo, second_topo = link_topologies(first_topo, second_topo,
                                              connection_type)
    first_ad.fill_from_topology(first_topo, clear=True)
    second_ad.fill_from_topology(second_topo, clear=True)


def get_some_trc_path(isd_id):
    dst_path = get_trc_file_path(isd_id, 0, isd_dir=GEN_PATH)
    components = os.path.normpath(dst_path).split(os.sep)

    components[-2] = 'AD*'
    files_glob = os.path.join(os.sep, *components)
    files = glob.glob(files_glob)
    if not files:
        raise Exception("No TRC files found: cannot generate the package")
    return files[0]


def create_new_ad_files(parent_ad_topo, isd_id, ad_id, out_dir):
    assert isinstance(parent_ad_topo, dict), 'Invalid topology dict'
    isd_ad_id = '{}-{}'.format(isd_id, ad_id)
    ad_dict = {
        "default_zookeepers": {"1": {"manage": False, "addr": "localhost"}},
        isd_ad_id: {'level': 'LEAF'},
    }
    gen = ConfigGenerator(out_dir=out_dir)

    path_policy_file = DEFAULT_PATH_POLICY_FILE
    zk_config = DEFAULT_ZK_CONFIG

    # Write basic config files for the new AD
    with tempfile.NamedTemporaryFile('w') as temp_fh:
        json.dump(ad_dict, temp_fh)
        temp_fh.flush()
        gen.generate_all(temp_fh.name, path_policy_file, zk_config)

    # Copy TRC file
    trc_path = get_some_trc_path(isd_id)
    if trc_path:
        dst_path = get_trc_file_path(isd_id, ad_id, isd_id, 0,
                                     isd_dir=out_dir)
        shutil.copyfile(trc_path, dst_path)

    new_topo_path = gen.path_dict(isd_id, ad_id)['topo_file_abs']
    new_topo_file = read_file(new_topo_path)
    new_topo = json.loads(new_topo_file)
    existing_topo, new_topo = link_topologies(parent_ad_topo, new_topo,
                                              'PARENT_CHILD')
    # Update the config files for the new AD
    write_file(new_topo_path, json.dumps(new_topo, sort_keys=4, indent=4))
    gen.write_derivatives(new_topo)
    return new_topo, existing_topo
