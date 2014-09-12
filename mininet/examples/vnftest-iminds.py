#!/usr/bin/python

"""
This example shows how to create an empty Mininet object
(without a topology object) and add nodes to it manually.
"""

from mininet.net import Mininet, MininetWithControlNet
from mininet.node import Controller, RemoteController
from mininet.cli import CLI
from mininet.log import setLogLevel, info

class InbandController( RemoteController ):

    def checkListening( self ):
        "Overridden to do nothing."
        return

def netWithVNFs(netconf = False):
    "Create an empty network and add nodes to it."

    #ctl = InbandController( 'ctl', ip='192.168.123.1' )
    #ctl = InbandController( 'ctl', ip='127.0.0.1' )
    #net = MininetWithControlNet( )
    net = MininetWithControlNet( controller=Controller, autoSetMacs=True )
    #net = Mininet( controller=Controller )

    info( '*** Adding controller\n' )
    ctl = net.addController( 'c0' , controller=RemoteController )
 
    #import pdb; pdb.set_trace();
    info( '*** Adding hosts \n' )
    h1 = net.addHost( 'h1')
    h2 = net.addHost( 'h2')

    info( '*** Adding VNFs \n' )

    if netconf:
        ee1 = net.addEE( 'ee1' )
        ee1.setVNF(vnf_name='netconf')
        ee2 = net.addEE( 'ee2' )
        ee2.setVNF(vnf_name='netconf')
        #[ exe1_sw, exe1_container ] = net.addManagedExe( 'exe1', nintf=5)
        #exe1_container.cmd = netconf.makeNetConfCmd()
    else:
        ee1 = net.addEE( 'ee1',cpu=0.1)
        #ee1.setVNF(vnf_name='fakeLoad', cpu='8', mem='5MB')
        ee1.setVNF(vnf_name='simpleForwarder', device=ee1.name+'_eth1',name=ee1.name)
        ee2 = net.addEE( 'ee2',cpu=0.1)

	#example for NAT with two ports connected to internal hosts (private addresses) and one port connected to the Internet (public address)
	device=[{'index':0,'name':'eth1','ip1':'1.0.0.1','ip2':'1.0.0.10'},{'index':1,'name':'eth2','ip1':'1.0.0.20','ip2':'1.0.0.30'}]
	public={'index':2,'name':'eth2'}
	ee2.setVNF(vnf_name='nat',device=device,public=public)
#        ee2.setVNF(vnf_name='simpleObservationPoint', name=ee2.name)
        #ee2.setVNF(vnf_name='fakeLoad', cpu='8', mem='5MB')
        #ee2.setVNF(vnf_name='lookbusy',
        #    mem_util='5MB', cpu_util='8-20', cpu_mode='curve',
        #    cpu_curve_period='5m', cpu_curve_peak='2m' )

    info( '*** Adding switches\n' )
    s3 = net.addSwitch( 's3' )
    s4 = net.addSwitch( 's4' )

    info( '*** Creating links\n' )
    net.addLink( h1, s3 )
    net.addLink( h2, s4 )
    net.addLink( s3, s4 )

    if netconf:
        net.addLink( exe1_sw, s3 )
    else:
        net.addLink( ee1, s3 )
        net.addLink( ee2, s4 )

    info( '*** Starting network\n' )
    net.start()

    info( '*** Running CLI\n' )
    CLI( net )

    info( '*** Stopping network' )
    net.stop()
    

def add_VNF():
	
    """ add VNFs to catalog (required parameters should be given) """

    from mininet.vnfcatalogiminds import Catalog

    #1. First single Click elements are added to the DB
    Catalog().add_VNF(vnf_name='FromDevice',vnf_type='Click')
    Catalog().add_VNF(vnf_name='ToDevice',vnf_type='Click')
    Catalog().add_VNF(vnf_name='Queue',vnf_type='Click')
    Catalog().add_VNF(vnf_name='Tee',vnf_type='Click')
    #Catalog().add_VNF(vnf_name='Counter',vnf_type='Click',clickPath='/home/click',
    #			clickSource=['elements/standard/counter.cc','elements/standard/counter.cc'])
    Catalog().add_VNF(vnf_name='Counter',vnf_type='Click')
    Catalog().add_VNF(vnf_name='Classifier',vnf_type='Click')
    Catalog().add_VNF(vnf_name='IPClassifier',vnf_type='Click')
    Catalog().add_VNF(vnf_name='ICMPPingSource',vnf_type='Click')
    Catalog().add_VNF(vnf_name='ARPQuerier',vnf_type='Click')
    Catalog().add_VNF(vnf_name='AggregateIPFlows',vnf_type='Click')
    Catalog().add_VNF(vnf_name='RFC2507Comp',vnf_type='Click')
    Catalog().add_VNF(vnf_name='RFC2507Decomp',vnf_type='Click')
    Catalog().add_VNF(vnf_name='IPAddRewriter',vnf_type='Click')   

    #2. Then the VNFs composed of several Click elements are added to the DB
    Catalog().add_VNF(vnf_name='simpleForwarder',vnf_type='Click',description='receive on the data interface and loop back the packet')
    Catalog().add_VNF(vnf_name='simpleObservationPoint',vnf_type='Click',description='A simple observation point in click')
    Catalog().add_VNF(vnf_name='headerCompressor',vnf_type='Click',description='Compress IPv4/TCP headers as defined in RFC2507')
    Catalog().add_VNF(vnf_name='headerDecompressor',vnf_type='Click',description='Decompress IPv4/TCP headers as defined in RFC2507')
    Catalog().add_VNF(vnf_name='nat',vnf_type='Click',description='Provide the functionality of basic network address translator')
    

if __name__ == '__main__':

    add_VNF()
    setLogLevel( 'info' )  
    netWithVNFs()
