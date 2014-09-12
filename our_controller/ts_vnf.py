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
H1_MAC = '00:00:00:00:00:01'
H2_MAC = '00:00:00:00:00:02'
S3_DPID = 3
S4_DPID = 4
S3_H1 = 1
S3_V1 = 3
S3_S4 = 2 
S4_S3 = 2
S4_V2 = 3
S4_H2 = 1

class TSTest (object):
  def __init__ (self):
    core.openflow.addListeners(self)
    core.TrafficSteering.addListeners(self)
    self._dpids = {}

    db_arp = { H1_IP: H1_MAC,
               H2_IP: H2_MAC
               }
    for ip, mac in db_arp.iteritems():
      core.Interactive.variables['arp'].set(ip, mac)

  def _handle_ConnectionUp (self, event):
    self._dpids[event.dpid] = 1
    s = sum(self._dpids.values())
    if s >= 2:
      log.error("sum: %s" % (s, ))
      routes = [
        [
          RouteHop(S3_DPID, S3_H1, S3_V1),
          RouteHop(S3_DPID, S3_V1, S3_S4),
          RouteHop(S4_DPID, S4_S3, S4_V2),
          RouteHop(S4_DPID, S4_V2, S4_H2)
        ],
        [
          RouteHop(S4_DPID, S4_H2, S4_S3),
          RouteHop(S3_DPID, S3_S4, S3_H1)
        ]
      ]
      for i, r in enumerate(routes):
        core.TrafficSteering.add_route(i, r)

  def _handle_ConnectionDown (self, event):
    self._dpids[event.dpid] = 0

  def _handle_RouteChanged (self, event):
    log.error('RouteChanged: %s' % event)

def launch ():
  core.register(TSTest())
