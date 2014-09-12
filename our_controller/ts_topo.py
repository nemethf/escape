"""Custom topology

   h1 -       --s6--     -- h3
       \     /      \   /
        \   /        \ /
   h2 -- s5 -------- s7 --- h4

h1: ip=10.0.0.1 mac=00:00:00:00:00:01     s5: dpid=00-00-00-00-00-05
h2: ip=10.0.0.2 mac=00:00:00:00:00:02     s6: dpid=00-00-00-00-00-06
h3: ip=10.0.0.3 mac=00:00:00:00:00:03     s7: dpid=00-00-00-00-00-07
h4: ip=10.0.0.4 mac=00:00:00:00:00:04

start as:
  sudo -E mn --custom topo.py --controller=remote --mac --switch=user
"""

from mininet.topo import Topo

class MyTopo( Topo ):
    "Simple topology example."

    def __init__( self ):
        "Create custom topo."

        # Initialize topology
        Topo.__init__( self )

        # Add hosts and switches
        h1 = self.addHost( 'h1' )
        h2 = self.addHost( 'h2' )
        h3 = self.addHost( 'h3' )
        h4 = self.addHost( 'h4' )
        s5 = self.addSwitch( 's5' )
        s6 = self.addSwitch( 's6' )
        s7 = self.addSwitch( 's7' )

        # Add links
        self.addLink( s5, h1 )
        self.addLink( s5, h2 )
        self.addLink( s5, s7 )
        self.addLink( s5, s6 )
        self.addLink( s6, s7 )
        self.addLink( s7, h3 )
        self.addLink( s7, h4 )

topos = { 'minimal': ( lambda: MyTopo() ) }
