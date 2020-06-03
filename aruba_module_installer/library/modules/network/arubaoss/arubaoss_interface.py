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
    configuration:
        description:
            - List of interface configurations
        required: true
        type: list
        elements: dict
        suboptions:
            interface:
                description:
                    - Comma separated list of interfaces and interface ranges to use this configuration.
                    - The keyword C(all) will configure all available interfaces on the switch.
                    - Example: C(1/1-2/1,2/4) will configure all of the interfaces on the first stack member, 
                    interface 1 on the second stacking member, and interface 4 on the second stack member.
                    - If the lower-bound or upper-bound of a range don't exist on the switch, the module
                    figures out which ports on the switch I(would) be within that range.
                    - Example: C(1/1-1/999) would match all built-in interfaces on the first stack member 
                    and none of the modules.
                    - Example: C(1/A1-1/FF) would match all modules on the first stack member and none of 
                    the built-in interfaces.
                    - Example: C(1/1-2/999) would match all built-in interfaces I(and) modules on the first 
                    stack member, and only the built-in interfaces on the second stack member.
                    - When determining which interfaces/modules on the switch are included in a range, I(all) 
                    interfaces I(and) modules on a lower stack member precede any interface or module on a 
                    higher stack member. E.g., C(1/B2) precedes C(2/1).
                    - Then, built-in interfaces (plain numbers) precede modules (letter + number) on the same 
                    stack member. E.g., C(1/999) precedes C(1/A1)
                    - Finally, lower interfaces precede higher interfaces, and lower modules precede higher modules. 
                    E.g., C(1/1) precedes C(1/3), C(1/A1) precedes C(1/A2), and C(1/A2) precedes C(1/B1).
                required: true
                type: str
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
                    - Required with acl_id
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
from collections import OrderedDict

QPTQOS = '~QPT_QOS'

class PortListError(Exception):
    # Raised when something is wrong with the user's port list
    def __init__(self, message):
        self.message = message

class PortRange:
    def __init__(self, spec):
        self._all = (spec == "all")
        if not self._all:
            # Parses the string to get the list of ranges provided by the user
            ranges = spec.replace(' ', '').split(',')
            ranges = list(map(lambda item: item.split('-'), ranges))
            for item in ranges:
                for port in item:
                    if re.fullmatch(r'[a-zA-Z]?\d+(/[a-zA-Z]?\d+)*', port) is None:
                        raise PortListError("{} isn't a valid port. Expected 0 or 1 letters followed by an integer. Example: 1, 43, A2, B3".format(port))
                if len(item) > 2:
                    # Return an error, user put in something like "1/1 - 1/4 - 1/9"
                    raise PortListError('{} is not a valid range. Ranges must specify one least port and one greatest port. Example: 1/1 - 1/2 - 1/3 (incorrect); 1/1 - 1/3 (correct)'.format('-'.join(item)))
                if len(item) == 2:
                    if self._precedes(item[1], item[0]):
                        # user put an upper bound before a lower bound
                        raise PortListError('{} - {} is not a valid range, did you mean {} - {}?'.format(item[0], item[1], item[1], item[0]))
            self._ranges = ranges

    def _precedes(self, left, right):
        # takes two ports like 1/123 and 2/A4, and returns true if the left comes before the right.
        # first compares the chassis, then compares the modules/ports.
        left_list = left.split('/')
        right_list = right.split('/')
        if len(left_list) != len(right_list):
            # Return an error, user gave a range like "1/1 - 3"
            raise PortListError('{} - {} is not a valid range. Example: 1/1 - 3 (incorrect); 1/1 - 2/3 (correct)'.format(left, right))
        for left_element, right_element in zip(left_list, right_list):
            if left_element != right_element:
                return self._number_precedes(left_element, right_element)
        return False # The ports are equivalent

    def _number_precedes(self, left, right):
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

    def includes(self, port):
        if self._all:
            return True
        else:
            for item in self._ranges:
                if item[0] == port:
                    return True
                elif len(item) == 2:
                    if (self._precedes(port, item[1]) and self._precedes(item[0], port)) or port == item[1]:
                        return True
            return False
    
    def select_ports(self, available_ports):
        selected_ports = [port for port in available_ports if self.includes(port)]
        return selected_ports

def get_available_ports(module):
    # Returns available ports on the device
    url = '/ports'
    response = get_config(module ,url)
    response = module.from_json(to_text(response))
    available_ports = set(map(lambda item: item['id'], response['port_element']))
    return available_ports

def config_port(module, params, port):
    url = '/ports/'+  port

    data = {'id': port}

    if params.get('description') != None:
        data['name'] =  params['description']

    if params.get('admin_stat') != None:
        data['is_port_enabled'] = params['admin_stat']

    result = run_commands(module, url, data, 'PUT',check=url)

    return result


def qos(module, params, port):
    # check qos policy is present
    qos_check = '/qos/policies/' + params['qos_policy'] + QPTQOS
    if not get_config(module, qos_check):
        return dict(changed=False, msg='Configure QoS policy first. {} does not exist'.format(params['qos_policy']))

    url = '/qos/ports-policies'

    if params['state'] == 'create':
        policy_id = params['qos_policy'] + QPTQOS
        port_config = get_config(module, url)
        if port_config:
            check_config = module.from_json(to_text(port_config))
            for ports in check_config['qos_port_policy_element']:
                if ports['port_id'] == port and \
                   ports['policy_id'] == policy_id and \
                   ports['direction'] == params['qos_direction']:
                       ret = {'changed':False}
                       ret.update(ports)
                       return ret


        data = {
                'port_id': port,
                'policy_id': policy_id,
                'direction': params['qos_direction']
                }
        result = run_commands(module, url,data, 'POST' )

    else:
        url_delete =  url + '/' + port + '-' + params['qos_policy'] + QPTQOS + '-' + params['qos_direction']
        check_url = url + '/' + port + '-' + params['qos_policy'] + QPTQOS + '/stats'
        result = run_commands(module, url_delete, {}, 'DELETE', check= check_url)
    return result



def acl(module, params, port):
    # Check if acl is present
    check_acl = '/acls/' + params['acl_id'] + "~" + params['acl_type']
    if not get_config(module,check_acl):
        return dict(changed=False, msg='Configure ACL first. {} does not exist'.format(module.params['acl_id']))

    url = "/ports-access-groups"
    acl_type = params['acl_type']
    direction = params['acl_direction']
    data = {'port_id': port,
            'acl_id': params['acl_id'] + "~" + acl_type,
            'direction': direction}

    delete_url = url + '/' + port + '-' + params['acl_id'] + "~" + acl_type\
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

def configurationPartOf(configuration_element):
    configPart = dict()
    for k, v in configuration_element.items():
        if k != 'interface':
            configPart[k] = v
    return configPart

def run_module():
    module_args = dict(
        configuration=dict(type='list', required=True, elements='dict', options=dict(
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
        ))
    )

    module_args.update(arubaoss_argument_spec)

    required_together = [('acl_id', 'acl_direction')]
    module = AnsibleModule(
        required_if=arubaoss_required_if,
        required_together=required_together,
        argument_spec=module_args,
        supports_check_mode=True
    )

    available_ports = get_available_ports(module)
    staged_changes = OrderedDict()

    for section in module.params['configuration']:
        try:
            port_range = PortRange(spec=section['interface'])
        except PortListError as err:
            module.fail_json(changed=False, msg=err.message)
        
        selected_ports = port_range.select_ports(available_ports)
        if selected_ports:
            changes = configurationPartOf(section)
            for port in selected_ports:
                staged_changes.update({port: changes})
        else:
            module.warn("{} did not match any ports on the switch, skipping this config section.".format(section['interface']))

    if not staged_changes:
        module.exit_json(skipped=True, msg='No ports were matched on the device.')

    if module.check_mode:
        module.exit_json(changed=False, staged_changes=staged_changes, warnings='Not Supported')

    try:
        result = dict(changed=False)
        qos_return = dict(changed=False, ports=dict())
        acl_return = dict(changed=False, ports=dict())
        config_return = dict(changed=False, ports=dict())
        for port, changes in staged_changes.items():
            if changes['qos_policy']:
                qos_result = qos(module=module, params=changes, port=port)
                qos_return['changed'] = qos_return['changed'] or qos_result['changed']
                qos_return['ports'][port] = qos_result

            if changes['acl_id']:
                acl_result = acl(module=module, params=changes, port=port)
                acl_return['changed'] = acl_return['changed'] or acl_result['changed']
                acl_return['ports'][port] = acl_result

            if changes['description'] or changes['admin_stat']:
                config_result = config_port(module=module, params=changes, port=port)
                config_return['changed'] = config_return['changed'] or config_result['changed']
                config_return['ports'][port] = config_result

        result['changed'] = qos_return['changed'] or acl_return['changed'] or config_return['changed']
        if qos_return['ports']:
            result['qos'] = qos_return
        if acl_return['ports']:
            result['acl'] = acl_return
        if config_return['ports']:
            result['config'] = config_return
        module.exit_json(**result)

    except Exception as err:
        return module.fail_json(changed=False, msg=err)


def main():
    run_module()

if __name__ == '__main__':
    main()
