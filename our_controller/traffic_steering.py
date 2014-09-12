# Copyright (c) 2014 Felician Nemeth
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
# along with POX. If not, see <http://www.gnu.org/licenses/>.

"""
Installs routes proactively.
"""

import pox
from pox.lib.util import dpid_to_str
from pox.lib.revent import *
from pox.lib.addresses import EthAddr
import pox.openflow.libopenflow_01 as of


ROUTE_FAILED   = 1
ROUTE_PENDING  = 2 # not used by traffic_streering, means:
                   # route is not ready for calling add_route()
ROUTE_STARTING = 3 # waiting for topology information
ROUTE_STARTED  = 4
ROUTE_REMOVING = 5
ROUTE_REMOVED  = 6

log = None

class RouteChanged (Event):
  FAILED   = ROUTE_FAILED
  PENDING  = ROUTE_PENDING
  STARTING = ROUTE_STARTING
  STARTED  = ROUTE_STARTED
  REMOVING = ROUTE_REMOVING
  REMOVED  = ROUTE_REMOVED

  def __init__ (self, id, status):
    Event.__init__(self)
    self.id = id
    self.status = status

  @classmethod
  def get_status_str (cls, status):
    s = {cls.FAILED: "failed",
         cls.PENDING: "pending",
         cls.STARTING: "starting",
         cls.STARTED: "started",
         cls.REMOVING: "removing",
         cls.REMOVED: "removed",
         }

    return s.get(status, status)

  def __str__ (self):
    return "id(%s)-status(%s)" % (self.id, self.get_status_str(self.status))

class RouteHop (object):
  INIT = 1
  SENT = 2
  INSTALLED = 3
  SENT_REMOVE = 4
  REMOVED = 5

  def __init__ (self, dpid, in_port, out_port,
                match = None, route_id = None):
    self.dpid = dpid
    self.route_id = route_id
    self.status = self.INIT
    self.in_port = in_port
    self.out_port = out_port
    self.set_dst_mac = None
    self.match_dst_mac = None
    self.match = match

  def get_flow_mod (self):

    flow_mod = of.ofp_flow_mod()
    if self.match:
      flow_mod.match = match
    if self.in_port:
      flow_mod.match.in_port = self.in_port

    if self.match_dst_mac:
      flow_mod.match.dl_dst = EthAddr(self.match_dst_mac)
    if self.set_dst_mac:
      action = of.ofp_action_dl_addr.set_dst(EthAddr(self.set_dst_mac))
      flow_mod.actions.append(action)

    out_action = of.ofp_action_output(port = self.out_port)
    flow_mod.actions.append(out_action)

    return flow_mod

  def __str__ (self):
    s = {self.INIT: "init",
         self.SENT: "sent",
         self.INSTALLED: "installed",
         self.SENT_REMOVE: "delete sent",
         self.REMOVED: "removed",
         }
    return "route(%s)-dp(%s)-status(%s)" % (
      self.route_id, self.dpid, s[self.status])

# #################################################################

class TrafficSteering  (EventMixin):
  """Install routes proactively."""
  _eventMixin_events = set([
    RouteChanged,
    ])

  class Route (object):
    def __init__ (self, id, hops = None):
      self.hops = hops
      self.id = id
      self.status = ROUTE_REMOVED

    def _is_tail_ready (self):
      hops = self.hops[1:]
      s = [ hop.status == RouteHop.INSTALLED for hop in hops ]
      return all(s)

    def _is_route_ready (self):
      s = [ hop.status == RouteHop.INSTALLED for hop in self.hops ]
      return all(s)

    def _is_route_removed (self):
      s = [ hop.status == RouteHop.REMOVED for hop in self.hops ]
      return all(s)

  def __init__ (self):
    self._routes = {}
    self._pending_barriers = {}
    self._xid_generator = of.xid_generator()
    pox.core.core.addListeners(self)
    pox.core.core.openflow.addListeners(self)
    pox.core.core.listen_to_dependencies(self)

  def add_route (self, id, route):
    log.debug('add_route: %s', id)

    error = not all([type(hop) == RouteHop for hop in route])
    error = error or len(route) == 0
    if error:
      log.error('invaild route: %s', route)
      pox.core.core.raiseLater(self, RouteChanged, id, RouteChanged.FAILED)
      return

    for hop in route:
      hop.route_id = id
    self._routes[id] = self.Route(id, route)
    self._install_route(id)

  def remove_route (self, id):
    self._change_route_status(self._routes[id], RouteChanged.REMOVING)
    for hop in self._routes.get(id).hops:
      self._remove_hop(hop)

  def _install_route (self, id):
    if not self._add_dst_mac_matching(id):
      self._change_route_status(self._routes[id], RouteChanged.STARTING)
      return

    for hop in self._routes[id].hops:
      log.debug('add_route: %s,%s', id, hop)
      self._install_hop(hop)

  def _add_dst_mac_matching (self, id):
    """
    Modifies a route by matching destination mac address.

    If a packet leaves a node or NF, then the dst_mac is set,
    otherwise the packet is forwarded iif the dst_mac is present.

    Examples:
    (dmac means destination mac address, "<-" means set, and
    "m" means match)

    SRC--> sw -----------> sw ----> VNF_1 ---> sw ----> sw ------> DST
        match:in_port  m:in_port          m:in_port  m:in_port
        dmac<-VNF_1    m:dmac==VNF_1      dmac<-DST  m:dmac==DST
                       dmac<-DST

    VNF_1 ---> sw ---> VNF_2
          m:in_port
          dmac<-DST
    """
    last_mac = None
    mac = None
    t = pox.core.core.SimpleTopology
    hops = self._routes[id].hops

    for hop in reversed(hops):
      # next node
      n_id, n_port_no, n_mac = t.get_other_end(hop.dpid, hop.out_port)
      if t.non_switch_node(n_id):
        mac = n_mac
        if not mac:
          return False
        if not last_mac:
          last_mac = mac
        hop.set_dst_mac = last_mac

      # previous node
      p_id, p_node_no, p_mac = t.get_other_end(hop.dpid, hop.in_port)
      if t.non_switch_node(p_id):
        if not hop.set_dst_mac:
          hop.set_dst_mac = mac
      else:
        hop.match_dst_mac = mac

    return True

  def _install_hop (self, hop):
    route = self._routes[hop.route_id]
    first = ( route.hops[0] == hop )
    if first and not route._is_tail_ready():
      return

    # send the flow_mod
    msg = hop.get_flow_mod()
    con = pox.core.core.openflow.getConnection(hop.dpid)
    if not con:
      # switch hasn't connected yet.
      # _handle_ConnectionUp will take care of the installation later
      return
    con.send(msg)

    # send the barrier
    barrier_xid = self._xid_generator()
    self._pending_barriers[barrier_xid] = hop
    hop.status = RouteHop.SENT
    con.send(of.ofp_barrier_request(xid=barrier_xid))

    log.debug('_install_hop:route_id(%s),dpid(%s),barrier(%s)',
              hop.route_id, hop.dpid, barrier_xid)

  def _remove_hop (self, hop):
    if hop.status != RouteHop.INSTALLED:
      log.error("route (%s): cannot remove hop from sw (%s)",
                hop.route_id, hop.dpid)
      return
    msg = hop.get_flow_mod()
    msg.command = of.OFPFC_DELETE_STRICT

    con = pox.core.core.openflow.getConnection(hop.dpid)
    if not con:
      # we could be more clever here.  Now, we assume the sw has
      # already been shut down.
      hop.status = RouteHop.REMOVED
      return
    con.send(msg)

    # send the barrier
    barrier_xid = self._xid_generator()
    self._pending_barriers[barrier_xid] = hop
    hop.status = RouteHop.SENT_REMOVE
    con.send(of.ofp_barrier_request(xid=barrier_xid))

    log.debug('_remove_hop:route_id(%s),dpid(%s),barrier(%s)',
              hop.route_id, hop.dpid, barrier_xid)

  def _change_route_status (self, route, new_status):
    if route.status == new_status:
      return

    log.debug('%s:%s->%s', route.id,
              RouteChanged.get_status_str(route.status),
              RouteChanged.get_status_str(new_status))

    route.status = new_status
    pox.core.core.raiseLater(self, RouteChanged, route.id, new_status)

  def _handle_SimpleTopology_RecentlyChanged (self, event):
    for id, r in self._routes.iteritems():
      if r.status == RouteChanged.STARTING:
        self._install_route(id)

  def _handle_BarrierIn (self, barrier):
    log.debug("_handle_BarrierIn: %s", barrier.xid)

    xid = barrier.xid
    dpid = barrier.dpid
    if xid not in self._pending_barriers:
      return EventContinue

    hop = self._pending_barriers.pop(xid)
    if hop.status == RouteHop.SENT:
      hop.status = RouteHop.INSTALLED
    elif hop.status == RouteHop.SENT_REMOVE:
      hop.status = RouteHop.REMOVED
    else:
      log.error('_handle_BarrierIn: inconsistent state (%s, %s)', xid, dpid)
      return EventHalt
    route = self._routes[hop.route_id]

    if route._is_route_removed():
      self._change_route_status(route, RouteChanged.REMOVED)
      del self._routes[hop.route_id]
    elif route._is_route_ready():
      self._change_route_status(route, RouteChanged.STARTED)
    elif route._is_tail_ready():
      self._install_hop(route.hops[0])

    return EventHalt

  def _handle_ConnectionDown (self, event):
    for r in self._routes.itervalues():
      for h in r.hops:
        if h.dpid == event.dpid:
          h.status = RouteHop.INIT
          self._change_route_status(r, ROUTE_FAILED)

  def _handle_ConnectionUp (self, event):
    for r in self._routes.itervalues():
      for hop in r.hops:
        if hop.dpid == event.dpid:
          self._install_hop(hop)


def launch ():
  global log
  log = pox.core.core.getLogger()
  pox.core.core.register(TrafficSteering())
