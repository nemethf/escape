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
    #ctl = net.addController( 'c0' )
 
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
        ee1 = net.addEE( 'ee1', cpu=0.5)
        # ee1.setVNF(vnf_name='fakeLoad', cpu='8', mem='5MB')
        # ee1.setVNF(vnf_name='simpleForwarder', name=ee1.name)
        ee1.setVNF(vnf_name='headerCompressor', name=ee1.name)
        ee2 = net.addEE( 'ee2', cpu=0.5)
        ee2.setVNF(vnf_name='headerDecompressor', name=ee2.name)
        # ee2.setVNF(vnf_name='fakeLoad', cpu='8', mem='5MB')

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

if __name__ == '__main__':
    setLogLevel( 'info' )
    netWithVNFs()
