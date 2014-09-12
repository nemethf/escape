#!/usr/bin/python

"""
This example shows how to create an empty Mininet object
(without a topology object) and add nodes to it manually.
"""

from mininet.net import Mininet
from mininet.node import Controller, RemoteController
from mininet.cli import CLI
from mininet.log import setLogLevel, info
from time import sleep

def netWithAgents():

    "Create an empty network and add nodes to it."

    net = Mininet( controller=Controller, autoSetMacs=True )

    info( '*** Adding controller\n' )
    #    ctl = net.addController( 'c0' , controller=RemoteController )
    ctl = net.addController( 'c0' , controller=Controller )

    info( '*** Adding hosts \n' )
    h1 = net.addHost( 'h1')
    h2 = net.addHost( 'h2')

    info( '*** Adding switches\n' )
    s3 = net.addSwitch( 's3' )
    s4 = net.addSwitch( 's4' )

    info( '*** Creating links\n' )
    net.addLink( h1, s3 )
    net.addLink( h2, s4 )
    net.addLink( s3, s4 )

    info( '*** Adding agents\n' )
    agt1 = net.addAgent( 'agt1' )
    agt2 = net.addAgent( 'agt2' )
    agt1.setSwitch( s3 )
    agt1.attachSwitch( s4 )
    agt2.setSwitch( s4 )

    info( '*** Starting network\n')
    net.start()

    info( '*** Running CLI\n' )
    CLI( net )

    info( '*** Stopping network' )
    net.stop()

if __name__ == '__main__':
    setLogLevel( 'info' )
    netWithAgents()
