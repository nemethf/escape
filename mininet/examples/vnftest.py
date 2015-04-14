#!/usr/bin/python

"""
This example shows how to create an empty Mininet object
(without a topology object) and add nodes and VNFs to it manually.
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
    "Create an empty network and add nodes and VNFs to it."

    net = MininetWithControlNet( controller=Controller, autoSetMacs=True )

    info( '*** Adding controller\n' )
    ctl = net.addController( 'c0' , controller=RemoteController )
 
    info( '*** Adding hosts \n' )
    h1 = net.addHost( 'h1')
    h2 = net.addHost( 'h2')

    info( '*** Adding VNFs \n' )

    if netconf:
        ee1 = net.addEE( 'ee1' )
        ee1.setVNF(vnf_name='netconf')
        ee2 = net.addEE( 'ee2' )
        ee2.setVNF(vnf_name='netconf')
    else:
        ee1 = net.addEE( 'ee1',cpu=0.1)
        ee1.setVNF(vnf_name='simpleForwarder', name=ee1.name)
        ee2 = net.addEE( 'ee2',cpu=0.1)
        #ee2.setVNF(vnf_name='fakeload', name=ee2.name, cpu='8', mem='5MB')
        ee2.setVNF(vnf_name='simpleForwarder')

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
