"""
start as
 $ ./pox.py log.color log.level --traffic_steering=DEBUG  traffic_steering proto.arp_responder ts_test

"""

from pox.core import core
from pox.lib.util import dpid_to_str
from pox.lib.packet.ethernet import ethernet, ETHER_BROADCAST
from pox.lib.addresses import *
from pox.lib.packet.ipv4 import ipv4
from pox.lib.revent import EventHalt, EventContinue
import pox.openflow.libopenflow_01 as of

from traffic_steering import *

log = core.getLogger()

H1_IP = '10.0.0.1'
H2_IP = '10.0.0.2'
H3_IP = '10.0.0.3'
H4_IP = '10.0.0.4'
H1_MAC = '00:00:00:00:00:01'
H2_MAC = '00:00:00:00:00:02'
H3_MAC = '00:00:00:00:00:03'
H4_MAC = '00:00:00:00:00:04'
S5_DPID = 5
S6_DPID = 6
S7_DPID = 7
S5_H1 = 1
S5_H2 = 2
S5_S6 = 4 
S5_S7 = 3
S6_S5 = 1
S6_S7 = 2
S7_H3 = 3
S7_H4 = 4
S7_S5 = 1
S7_S6 = 2

class TSTest (object):
  def __init__ (self):
    core.openflow.addListeners(self)
    core.TrafficSteering.addListeners(self)
    self._dpids = {}

    db_arp = { H1_IP: H1_MAC,
               H2_IP: H2_MAC,
               H3_IP: H3_MAC,
               H4_IP: H4_MAC}
    for ip, mac in db_arp.iteritems():
      core.Interactive.variables['arp'].set(ip, mac)

  def _handle_ConnectionUp (self, event):
    self._dpids[event.dpid] = 1
    s = sum(self._dpids.values())
    if s >= 3:
      log.error("sum: %s" % (s, ))
      routes = [
        [
          RouteHop(S5_DPID, S5_H1, S5_S7),
          RouteHop(S7_DPID, S7_S5, S7_H3)
        ],
        [
          RouteHop(S7_DPID, S7_H3, S7_S5),
          RouteHop(S5_DPID, S5_S7, S5_H1)
        ]
      ]
      for i, r in enumerate(routes):
        core.TrafficSteering.add_route(i, r)

  def _handle_RouteChanged (self, event):
    log.error('RouteChanged: %s' % event)

def launch ():
  core.register(TSTest())
