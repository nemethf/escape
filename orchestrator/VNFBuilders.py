# Copyright (c) 2014 Attila Csoma
#
# This file is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This file is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.

'''
Created on Jul 1, 2014

@author: csoma
'''
import copy
from mininet.vnfcatalog import Catalog
from Utils import Store

class VNFClickBuilder():

    def __init__(self):
        self.catalog = Catalog()

    def create_vnf(self, opts, host):
        options = copy.deepcopy(opts)
        host_name = getattr(host, 'name', None)
        if host_name is None:
            raise RuntimeError("Unsupported host type: %s"%type(host))
        vnf = Store()
        del options['name']
        vnf.startCmd = self.catalog.make_cmd(options['function'],
                                             name = host_name,
                                             **options)
        return vnf

class VNFDummyBuilder():
    pass
