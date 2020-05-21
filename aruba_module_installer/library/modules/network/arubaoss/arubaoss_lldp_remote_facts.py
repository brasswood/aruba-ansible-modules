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
module: arubaoss_lldp_facts

short_description: Shows lldp remote info on device

version_added: "2.9"

description:
    - "This module implements the REST API for getting lldp 
       remote info on the device."

extends_documentation_fragment:
    - arubaoss_rest

options:
    

author:
    - Andrew Riachi (@brasswood)

'''

EXAMPLES = r'''

'''

RETURN = r'''

'''