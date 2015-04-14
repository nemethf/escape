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
Maintains the network topology in operation.

Although we could submit the information we collect to POX's
topology.py, but this interface is simpler (and less powerful.)

Depends on:
* NetworkManager.py
"""

from pox.core import core
from pox.lib.revent import *

log = core.getLogger()

class RecentlyChanged (Event):
  """
  Fire when topology changed recently.

  Fire only once even if many changes happen in a short period of
  time.
  """
  pass


class SimpleTopology (EventMixin):
  """Maintain the network topology in operation."""
  _eventMixin_events = {RecentlyChanged}

  def __init__(self):
      super(SimpleTopology, self).__init__()
      self._nodes = {}
      self._timer = False
      core.listen_to_dependencies(self)

  def get_other_end (self, dpid, port_no):
    ### Get opposite node's name, port number, MAC address
    node = self.get_node_by_dpid(dpid)
    port = self._get_port_by_port_no(node, port_no)
    oe = port.get('other_end', {})
    o_id = oe.get('node_name')
    o_port_no = oe.get('port_no')
    o_mac  = oe.get('mac')

    return o_id, o_port_no, o_mac

  def non_switch_node (self, node_name):
    node = self.get_node_by_name(node_name)
    # type seems to be always -1

    # This is a bit of a hack, since VNF started by a netconf agent is
    # added as a RemoteSwitch with dpid=-1.  We should really use
    # RemoteHost instead.  But that does not exists at the moment.
    if node.get('dpid'):
      return node.get('dpid') < 0
    return True

  def get_node_ip_pairs (self):
    r = []
    for node_name, node in self._nodes.iteritems():
      if self.non_switch_node(node_name):
        for port in self._get_ports(node).itervalues():
          if not port.get('ip'):
            continue
          r.append((node_name, port['ip']))
    return r

  def get_node_by_name (self, name):
    if name not in self._nodes:
      self._nodes[name] = {}
    return self._nodes.get(name)

  def get_node_by_dpid (self, dpid):
    for node in self._nodes.itervalues():
      if node.get('dpid') == dpid:
        return node
    else:
      return None

  def _get_ports (self, node):
    if 'ports' not in node:
      node['ports'] = {}
    return node['ports']

  def _get_port_by_port_no (self, node, port_no):
    for port in self._get_ports(node).itervalues():
      if port.get('port_no') == port_no:
        return port
    else:
      return {}

  def _update_port (self, node1_name, intf1_name, node2_name, intf2_name):
    n1 = self.get_node_by_name(node1_name)
    n2 = self.get_node_by_name(node2_name)

    port1 = {}
    for port in self._get_ports(n1).itervalues():
      if port.get('id') == intf1_name:
        port1 = port
        break
    else:
      n1['ports'][intf1_name] = port1

    port2 = {}
    for port in self._get_ports(n2).itervalues():
      if port.get('id') == intf2_name:
        port2 = port
        break
    else:
      n2['ports'][intf2_name] = port2

    port1['other_end'] = port2
    port2['other_end'] = port1

  def _delete_port (self, node1_name, node2_name):
    delete = []
    node1 = self.get_node_by_name(node1_name)
    for intf_name, port in node1['ports'].iteritems():
      other_end = port.get('other_end')
      if other_end:
        if port['other_end']['node_name'] == node2_name:
          delete.append(intf_name)
    for intf_name in delete:
      del node1['ports'][intf_name]

  def _handle_NetworkManagerMininet_LinkChange (self, event):
    e = event
    log.debug('_handle_LinkChange:%s', repr(e.__dict__))
    if e.delete:
      self._delete_port(e.node1, e.node2)
    else:
      self._update_port(e.node1, e.intf1.name, e.node2, e.intf2.name)
    self._start_timer()

  def _handle_NetworkManagerMininet_NodeChange (self, event):
    log.debug('_handle_NodeChange:%s', repr(event.__dict__))

    if event.name is None:
      log.warn('NodeChange event has no name (%s)' , repr(event.__dict__))
      return
    if event.intf is None:
      log.warn('Missing info from Interface (%s)', event.name)
      return

    node_name = event.name
    if node_name not in self._nodes:
      self._nodes[node_name] = {}
    ports = self._nodes[event.name].get('ports', {})
    for intf_name, intf in event.intf.iteritems():
      port_no = intf.get('port')
      port = ports.get(intf_name, {})
      port['mac'] = intf['mac']
      port['ip'] = intf['ip']
      port['id'] = intf_name
      port['node_name'] = event.name
      port['port_no'] = port_no
      ports[intf_name] = port

    self._nodes[node_name]['ports'] = ports
    self._nodes[node_name]['dpid'] = event.dpid
    self._start_timer()

  def _start_timer (self):
    if self._timer:
      return # already ticking
    self._timer = True
    core.callDelayed(1, self._handle_timer)

  def _handle_timer (self):
    core.raiseLater(self, RecentlyChanged)
    self._timer = False

def launch ():
  core.register(SimpleTopology())
