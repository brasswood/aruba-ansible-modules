#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Copyright: (c) 2020, Andrew Riachi <ariachi@ku.edu>
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

DOCUMENTATION = r'''
---
module: arubaoss_lldp_remote_facts

short_description: Shows lldp remote info on device

version_added: "2.9"

description:
    - This module implements the REST API for getting lldp remote info on the device.

options: {}

notes:
    - You may need to use a filter plugin (or multiple) to handle the output from this module. 
      Luckily, if none provided by Ansible fit your needs, you can easily write one in python. 
    - See U(https://docs.ansible.com/ansible/latest/user_guide/playbooks_filters.html) and
      U(https://docs.ansible.com/ansible/latest/dev_guide/developing_plugins.html#filter-plugins) for
      more information about filter plugins.

author:
    - Andrew Riachi (@brasswood)

'''

EXAMPLES = r'''
- name: Get LLDP remote information and store it in a variable
  arubaoss_lldp_remote_facts:
  register: lldp

- name: Print LLDP information just gathered
  debug:
    var: lldp.remote_devices

- name: Just print the remote system names
  debug:
    msg: "{{ lldp.remote_devices | map(attribute='system_name') | list }}"
'''

RETURN = r'''
remote_devices:
    description: LLDP remote devices gathered from the switch
    returned: On success
    type: list
    elements: dict
    contains:
        local_port:
            description: Local port
            type: str

        chassis_type:
            description: Chassis type
            type: str

        chassis_id:
            description: Chassis ID
            type: str

        port_type:
            description: Port type
            type: str

        port_id:
            description: Port ID
            type: int

        port_description:
            description: Port description
            type: str
        
        system_name:
            description: System name
            type: str

        system_description:
            description: System description
            type: str
        
        pvid:
            description: pvid
            type: int
        
        capabilities_supported:
            description: System capabilities supported
            type: dict
            contains:
                repeater:
                    description: Whether the device is a repeater
                    type: bool
                
                bridge:
                    description: Whether the device is a bridge
                    type: bool

                wlan_access_point:
                    description: Whether the device is a wireless access point
                    type: bool
                
                router:
                    description: Whether the device is a router
                    type: bool
                
                telephone:
                    description: Whether the device is a telephone
                    type: bool

                cable_device:
                    description: Whether the device is a cable device
                    type: bool

                station_only:
                    description: Station only
                    type: bool

        capabilities_enabled:
            description: System capabilities enabled
            type: dict
            contains:
                repeater:
                    description: Whether the device is a repeater
                    type: bool
                
                bridge:
                    description: Whether the device is a bridge
                    type: bool

                wlan_access_point:
                    description: Whether the device is a wireless access point
                    type: bool
                
                router:
                    description: Whether the device is a router
                    type: bool
                
                telephone:
                    description: Whether the device is a telephone
                    type: bool

                cable_device:
                    description: Whether the device is a cable device
                    type: bool

                station_only:
                    description: Station only
                    type: bool

        remote_management_address:
            description: Remote management address
            type: dict
            contains:
                type:
                    description: Address family
                    type: str
                
                address:
                    description: Address
                    type: str

        poe_plus_info:
            description: Poe plus information detail, NA for oobm port.
            type: dict
            contains:
                poe_device_type:
                    description: Poe device type
                    type: str
                
                power_source:
                    description: Power source
                    type: str

                power_priority:
                    description: Power priority
                    type: str
                
                requested_power_in_watts:
                    description: Requested power value in watts
                    type: str

                actual_power_in_watts:
                    description: Actual power in watts
                    type: str
'''
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.network.arubaoss.arubaoss import arubaoss_argument_spec
from ansible.module_utils.network.arubaoss.arubaoss import run_commands

def run_module():
    module = AnsibleModule(
        argument_spec=arubaoss_argument_spec,
    )

    url = "/lldp/remote-device"
    data = {}
    method = "GET"

    response = run_commands(module, url, data, method)
    devices = response['lldp_remote_device_element']
    for device in devices:
        del device['uri']

    result = dict(
        changed=False,
        remote_devices=devices
    )
    module.exit_json(**result)


def main():
    run_module()

if __name__ == '__main__':
    main()