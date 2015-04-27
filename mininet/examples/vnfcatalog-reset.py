#!/usr/bin/python

# Copyright (c) 2014 iMinds, BME
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
#
# You should have received a copy of the GNU General Public License
# along with this file. If not, see <http://www.gnu.org/licenses/>.

"""
This example resets the vnf catalog.
"""

from mininet.vnfcatalog import Catalog

def del_VNFs(vnf_list):
    for vnf in vnf_list:
        if Catalog().get_VNF(vnf_name = vnf) != []:
            Catalog().remove_VNF(vnf_name = vnf)

def add_VNFs():
    """ add VNFs to catalog (required parameters should be given) """

    #1. First single Click elements are added to the DB
    Catalog().add_VNF(vnf_name='FromDevice',vnf_type='Click',hidden='True')
    Catalog().add_VNF(vnf_name='ToDevice',vnf_type='Click',hidden='True')
    Catalog().add_VNF(vnf_name='Queue',vnf_type='Click',hidden='True')
    Catalog().add_VNF(vnf_name='Tee',vnf_type='Click',hidden='True')
    #Catalog().add_VNF(vnf_name='Counter',vnf_type='Click',clickPath='/home/click',
    #			clickSource=['elements/standard/counter.cc','elements/standard/counter.cc'])
    Catalog().add_VNF(vnf_name='Counter',vnf_type='Click',hidden='True')
    Catalog().add_VNF(vnf_name='Classifier',vnf_type='Click',hidden='True')
    Catalog().add_VNF(vnf_name='IPClassifier',vnf_type='Click',hidden='True')
    Catalog().add_VNF(vnf_name='StripIPHeader',vnf_type='Click',hidden='True')
    Catalog().add_VNF(vnf_name='UnstripIPHeadet',vnf_type='Click',hidden='True')
    Catalog().add_VNF(vnf_name='Strip',vnf_type='Click',hidden='True')
    Catalog().add_VNF(vnf_name='Unstrip',vnf_type='Click',hidden='True')
    Catalog().add_VNF(vnf_name='ICMPPingSource',vnf_type='Click',hidden='True')
    Catalog().add_VNF(vnf_name='ARPQuerier',vnf_type='Click',hidden='True')
    Catalog().add_VNF(vnf_name='AggregateIPFlows',vnf_type='Click',hidden='True')
    Catalog().add_VNF(vnf_name='RFC2507Comp',vnf_type='Click',hidden='True')
    Catalog().add_VNF(vnf_name='RFC2507Decomp',vnf_type='Click',hidden='True')
    Catalog().add_VNF(vnf_name='IPAddRewriter',vnf_type='Click',hidden='True')

    Catalog().add_VNF(vnf_name='TCPOptimizer',vnf_type='Click',hidden='True')
    Catalog().add_VNF(vnf_name='MarkIPHeader',vnf_type='Click',hidden='True')

    Catalog().add_VNF(vnf_name='Print',vnf_type='Click',hidden='True')

    #2. Then the VNFs composed of several Click elements are added to the DB
    Catalog().add_VNF(vnf_name = 'simpleForwarder',
                      vnf_type = 'Click',
                      description = 'receive on the data interface and loop back the packet',
                      icon = 'forward.png')
    Catalog().add_VNF(vnf_name = 'simpleObservationPoint',
                      vnf_type = 'Click',
                      description = 'A simple observation point in click',
                      icon = 'search.png')
    Catalog().add_VNF(vnf_name = 'headerCompressor',
                      vnf_type = 'Click',
                      description = 'Compress IPv4/TCP headers as defined in RFC2507',
                      icon = 'decompress_small.png')
    Catalog().add_VNF(vnf_name = 'headerDecompressor',
                      vnf_type = 'Click',
                      description = 'Decompress IPv4/TCP headers as defined in RFC2507',
                      icon = 'compress2_small.png')
    Catalog().add_VNF(vnf_name = 'nat',
                      vnf_type = 'Click',
                      hidden = 'True',
                      description = 'Provide the functionality of basic network address translator')
    Catalog().add_VNF(vnf_name = 'tcpRWINOptimizer',
                      vnf_type = 'Click',
                      description = 'TCP Optimizer',
                      icon = 'forward.png')
    Catalog().add_VNF(vnf_name = 'testVNF',
                      vnf_type = 'Click',
                      description = 'A test VNF',
                      icon = 'forward.png')
    Catalog().add_VNF(vnf_name = 'RlncOnTheFlyEncoder',
                      vnf_type = 'Click',
                      description = 'Rlnc encoder with kodo.',
                      icon = 'forward.png')
    Catalog().add_VNF(vnf_name = 'RlncOnTheFlyDecoder',
                      vnf_type = 'Click',
                      description = 'Rlnc decoder with kodo',
                      icon = 'forward.png')
    Catalog().add_VNF(vnf_name = 'FullRlncEncoder',
                      vnf_type = 'Click',
                      description = 'Full rlnc encoder with kodo.',
                      icon = 'forward.png')
    Catalog().add_VNF(vnf_name = 'FullRlncDecoder',
                      vnf_type = 'Click',
                      description = 'Full rlnc decoder with kodo',
                      icon = 'forward.png')
    Catalog().add_VNF(vnf_name = 'FullRlncRecoder',
                      vnf_type = 'Click',
                      description = 'Full rlnc recoder with kodo',
                      icon = 'forward.png')

    print Catalog().get_db()

if __name__ == '__main__':

    del_VNFs(['simpleForwarder',
              'simpleObservationPoint',
              'headerCompressor',
              'headerDecompressor',
              'tcpRWINOptimizer',
              'nat',
              'testVNF',
              'FullRlncEncoder',
              'FullRlncDecoder',
              'FullRlncRecoder',
              'RlncOnTheFlyEncoder',
              'RlncOnTheFlyDecoder'])

    add_VNFs()
