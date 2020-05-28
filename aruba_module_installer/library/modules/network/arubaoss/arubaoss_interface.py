#!/usr/bin/python
#
# Copyright (c) 2019 Hewlett Packard Enterprise Development LP
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied. See the License for the
# specific language governing permissions and limitations
# under the License.

ANSIBLE_METADATA = {
    'metadata_version': '1.1',
    'status': ['preview'],
    'supported_by': 'community'
}

DOCUMENTATION = '''
---
module: arubaoss_interface

short_description: Implements Ansible module for port configuration
                   and management.

version_added: "2.6"

description:
    - "This implement rest api's which can be used to configure ports"

extends_documentation_fragment:
    - arubaoss_rest

options:
    interface:
        description:
            - interface id to be configured
        required: true
    description:
        description:
            - interface name/description, to remove the description of an interface
            pass in an empty string ''
        required: false
    admin_stat:
        description:
            - interface admin status
        required: false
    qos_policy:
        description:
            - Name of QOS policy profile that needs to applied to port
        required: false
    acl_id:
        description:
            - Name ACL profile that needs to applied to port
        required: false
    acl_direction:
        description:
            - Direction in which ACL will be applied.
        required: false


author:
    - Ashish Pant (@hpe)
'''

EXAMPLES = '''
     - name: configure port description
       arubaoss_interface:
         interface: 1
         description: "test_interface"

      - name: configure qos on port
        arubaoss_interface:
          interface: 5
          qos_policy: "my_qos"

      - name: delete qos from port
        arubaoss_interface:
          interface: 5
          qos_policy: "my_qos"
          enable: False

      - name: config acl on ports
        arubaoss_interface:
          interface: 2
          acl_id: test
          acl_type: standard
          acl_direction: in

      - name: delete acl ports stats
        arubaoss_interface:
          state: delete
          interface: 2
          acl_id: test
          acl_type: standard
          acl_direction: in

'''

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.network.arubaoss.arubaoss import run_commands,get_config
from ansible.module_utils.network.arubaoss.arubaoss import arubaoss_argument_spec, arubaoss_required_if
from ansible.module_utils._text import to_text
import re

QPTQOS = '~QPT_QOS'

class PortListError(Exception):
    # Raised when something is wrong with the user's port list
    def __init__(self, message):
        self.message = message

def get_available_ports(module):
    # Returns available ports on the device
    url = '/ports'
    response = get_config(module ,url)
    response = module.from_json(to_text(response))
    available_ports = set(map(lambda item: item['id'], response['port_element']))
    return available_ports

def get_selected_ports(port_list, available_ports):
    # Returns a list of all ports the user selected that are on the switch
    if port_list == 'all':
        return available_ports

    ranges = parse_port_list(port_list)
    selected_ports = set()
    for item in ranges:
        if item[0] in available_ports:
            selected_ports.add(item[0])
        if len(item) == 2:
            for available_port in available_ports:
                if (precedes(available_port, item[1]) and precedes(item[0], available_port)) or available_port == item[1]:
                    selected_ports.add(available_port)        
    return selected_ports

def parse_port_list(port_list):
    # Helper function to make sure the port list provided is OK
    # Takes a string, returns a list of lists for get_selected_ports
    ranges = port_list.replace(' ', '').split(',')
    ranges = list(map(lambda item: item.split('-'), ranges))
    for item in ranges:
        for port in item:
            if re.fullmatch(r'[a-zA-Z]?\d+(/[a-zA-Z]?\d+)*', port) is None:
                raise PortListError("{} isn't a valid port. Expected 0 or 1 letters followed by an integer. Example: 1, 43, A2, B3".format(port))
        if len(item) > 2:
            # Return an error, user put in something like "1/1 - 1/4 - 1/9"
            raise PortListError('{} is not a valid range. Ranges must specify one least port and one greatest port. Example: 1/1 - 1/2 - 1/3 (incorrect); 1/1 - 1/3 (correct)'.format('-'.join(item)))
        if len(item) == 2:
            if precedes(item[1], item[0]):
                # user put an upper bound before a lower bound
                raise PortListError('{} - {} is not a valid range, did you mean {} - {}?'.format(item[0], item[1], item[1], item[0]))
    return ranges

def precedes(left, right):
    # takes two ports like 1/123 and 2/A4, and returns true if the left comes before the right.
    # first compares the chassis, then compares the modules/ports.
    left_list = left.split('/')
    right_list = right.split('/')
    if len(left_list) != len(right_list):
        # Return an error, user gave a range like "1/1 - 3"
        raise PortListError('{} - {} is not a valid range. Example: 1/1 - 3 (incorrect); 1/1 - 2/3 (correct)'.format(left, right))
    for left_element, right_element in zip(left_list, right_list):
        if left_element != right_element:
            return number_precedes(left_element, right_element)
    return False # The ports are equivalent

def number_precedes(left, right):
    # takes two numbers like 123 and A4, and returns true if the left comes before the right.
    # in this function, normal ports always precede modules.
    if left[0].isalpha() != right[0].isalpha():
        return ((not left[0].isalpha()) and right[0].isalpha())
    elif left[0].isalpha() and right[0].isalpha():
        if left[0].upper() < right[0].upper():
            return True
        elif left[0].upper() > right[0].upper():
            return False
        else:
            return int(left[1:]) < int(right[1:])
    else:
        return int(left) < int(right)

def config_port(module):

    params = module.params
    url = '/ports/'+  module.params['interface']

    data = {'id': params['interface']}

    if params.get('description') != None:
        data['name'] =  params['description']

    if params.get('admin_stat') != None:
        data['is_port_enabled'] = params['admin_stat']

    result = run_commands(module, url, data, 'PUT',check=url)

    return result


def qos(module):

    params = module.params

    url = '/qos/ports-policies'
    qptqos = '~QPT_QOS'

    # check qos policy is present
    qos_check = '/qos/policies/' + params['qos_policy'] + qptqos
    if not get_config(module, qos_check):
        return {'msg': 'Configure QoS policy first. {} does not exist'.\
                format(params['qos_policy']),'changed':False}


    if params['state'] == 'create':
        policy_id = params['qos_policy'] + qptqos
        port_config = get_config(module, url)
        if port_config:
            check_config = module.from_json(to_text(port_config))
            for ports in check_config['qos_port_policy_element']:
                if ports['port_id'] == params['interface'] and \
                   ports['policy_id'] == policy_id and \
                   ports['direction'] == params['qos_direction']:
                       ret = {'changed':False}
                       ret.update(ports)
                       return ret


        data = {
                'port_id': params['interface'],
                'policy_id': policy_id,
                'direction': params['qos_direction']
                }
        result = run_commands(module, url,data, 'POST' )

    else:
        url_delete =  url + '/' + params['interface'] + '-' + params['qos_policy'] + qptqos + '-' + params['qos_direction']
        check_url = url + '/' + params['interface'] + '-' + params['qos_policy'] + qptqos + '/stats'
        result = run_commands(module, url_delete, {}, 'DELETE', check= check_url)
    return result


def acl(module):

    params = module.params

    if params.get('acl_direction') is None:
        return {'msg': 'Missing parameter: acl_direction','changed':False}

    # Check if acl is present
    url = "/ports-access-groups"
    acl_type = params['acl_type']
    direction = params['acl_direction']
    data = {'port_id': params['interface'],
            'acl_id': params['acl_id'] + "~" + acl_type,
            'direction': direction}

    check_acl = '/acls/' + params['acl_id'] + "~" + acl_type
    if not get_config(module,check_acl):
        return {'msg': 'Configure ACL first. {} does not exist'.\
                                format(params['acl_id']),'changed':False}

    delete_url = url + '/' + params['interface'] + '-' + params['acl_id'] + "~" + acl_type\
            + '-' +  direction

    config_present = False
    current_acl = get_config(module,url)
    if current_acl:
        check_config = module.from_json(to_text(current_acl))

        for ele in check_config['acl_port_policy_element']:
            if ele['uri'] == delete_url:
                config_present = ele


    if params['state'] == 'create':
        if config_present:
            ret = {'changed': False}
            ret.update(ele)
            return ret
        else:
            result = run_commands(module, url, data, method='POST')
    else:
        if config_present:
            result = run_commands(module, delete_url, method='DELETE')
        else:
            return {'changed': False,'failed': False, 'msg': 'Not present'}

    return result


def run_module():
    module_args = dict(
        interface=dict(type='str', required=True),
        description=dict(type='str', required=False),
        admin_stat=dict(type='bool', required=False),
        qos_policy=dict(type='str', required=False),
        qos_direction=dict(type='str', required=False, default='QPPD_INBOUND',
            choices=['QPPD_INBOUND','QPPD_OUTBOUND']),
        state=dict(type='str', required=False, default='create',
            choices=['create','delete']),
        acl_id=dict(type='str', required=False),
        acl_type=dict(type='str', required=False, default='AT_STANDARD_IPV4',
            choices=['AT_STANDARD_IPV4','AT_EXTENDED_IPV4','AT_CONNECTION_RATE_FILTER']),
        acl_direction=dict(type='str', required=False, choices=['AD_INBOUND',
            'AD_OUTBOUND','AD_CRF']),
    )

    module_args.update(arubaoss_argument_spec)

    result = dict(changed=False,warnings='Not Supported')

    module = AnsibleModule(
        required_if=arubaoss_required_if,
        argument_spec=module_args,
        supports_check_mode=True
    )

    if module.check_mode:
        module.exit_json(**result)

    available_ports = get_available_ports(module)
    selected_ports = get_selected_ports(module, available_ports)

    ports = str(module.params['interface']).replace(' ', '').split('-')

    port_url = '/ports/' + str(module.params['interface'])
    check_port = get_config(module,port_url)
    if not check_port:
        result = {'msg': 'Port {} not present on device {}'.format(module.params['interface'],port_url),
                'changed':False}
    else:
        try:

            if module.params['qos_policy']:
                result = qos(module)
            elif module.params['acl_id']:
                result = acl(module)
            else:
                result = config_port(module)

        except Exception as err:
            return module.fail_json(msg=err)

    module.exit_json(**result)


def main():
    run_module()

if __name__ == '__main__':
    main()
