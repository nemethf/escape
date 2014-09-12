# Copyright (c) 2014 Attila Csoma
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
from copy import deepcopy

'''
Created on May 29, 2014

@author: Attila Csoma
'''

import networkx as nx
import logging
import threading
import re
import pox.lib
import Utils

from subprocess import call
from traffic_steering import RouteHop, RouteChanged
from networkx.readwrite import json_graph
from pox import core
from pox import boot
from pox.lib.revent.revent import EventMixin, Event
from mininet import clickgui
from mininet.net import Mininet
from mininet.cli import CLI
from mininet.vnfcatalog import Catalog

import VNFBuilders
from Utils import LoggerHelper
from NetconfHelper import NetconfHelper, RPCError
from ncclient.transport import AuthenticationError

class DefaultSorter(object):
    def order_vnf_list(self, vnf_list, chain_graph):
        req = dict()
        for vnf in vnf_list:
            req[vnf] = chain_graph.node[vnf]['req']
        def f(_id): return (req[_id]['cpu'], req[_id]['mem'])

        return [vnf_list[x] for x in sorted(req, key = f, reverse = True)]

    def get_node_for_vnf(self, vnf, chain_graph, res_graph):
        chosen_node = None
        chosen_node_id = None
        for res_node_id in res_graph.node:
            res_node = res_graph.node[res_node_id]
            #TODO: check if this comparison is correct in python
            if 'node_type' in res_node \
            and res_node['node_type'] == NetworkGraphManager.NODE_TYPE_HOST \
            and res_node['res'] >= vnf.node['req']:
                #TODO: link resource check
                if res_node['res'] >= chosen_node:
                    chosen_node = res_node['res']
                    chosen_node_id = res_node_id

        return chosen_node_id

class NetworkGraphManager(object):

    log = logging.getLogger(__name__)

    NODE_TYPE_SAP = "SAP"
    NODE_TYPE_VNF = "VNF"
    NODE_TYPE_HOST = "HOST"
    NODE_TYPE_SWITCH = "SW"
    NODE_TYPE_CONTROLLER = "C"

    def __init__(self, auto_id = False, views = ['CHAIN', 'PHY'],
                 algorithm = DefaultSorter, **config):

        self.log = NetworkGraphManager.log
        self.auto_id = auto_id
        self.config = dict()
        self.status = dict()
        self.graphs = dict()
        self.chains = dict()

        self.algorithm = algorithm()

        self.chain_counter = 0

        self.config['chain_view'] = "CHAIN"
        self.config['res_view'] = "PHY"

        for view in views:
            self.config[view] = Utils.Store()
            self.status[view] = Utils.Store()
            self.graphs[view] = Utils.Store()

            self.status[view].id_counter = 0
            self.graphs[view] = nx.Graph()

        self.config.update(config)

    def add_node(self, _id, view, **node_params):
        node_id = _id
        if self.auto_id:
            node_id = self._next_node_id(view)
        elif node_id is None:
            raise RuntimeError('node_id is Null but auto_id disabled')

        if node_id in self.graphs[view].node:
            raise RuntimeError("#%s node already in the graph %s"%(node_id, view))

        self.log._debug('Add #%s node with parameters %s to view %s'%(node_id, node_params, view))
        self.graphs[view].add_node(node_id, **node_params)

        return node_id

    def remove_node(self, _id, view):
        self.log._debug('Remove #%s node from %s view'%(_id, view))
        self.graphs[view].remove_node(_id)

    def modify_node(self, _id, view, **node_params):
        if _id not in self.graphs[view].node:
            raise RuntimeError("Can not find #%s node in %s"%(_id, view))

        self.log._debug('Modify #%s node in %s view. New parameters: %s'%(_id, view, node_params))
        self.graphs[view].add_node(_id, **node_params)

    def add_link(self, source, target, view, **link_params):
        self.log._debug('Add link between #%s - #%s nodes in %s view with parameters %s'%(source, target, view, link_params))
        self.graphs[view].add_edge(source, target, **link_params)

    def remove_link(self, source, target, view):
        self.log._debug('Remove link between #%s and #%s nodes from %s view'%(source, target, view))
        self.graphs[view].remove_edge(source, target)

    def modify_link(self, source, target, view, **link_params):
        self.log._debug('Modify link between #%s and #%s nodes in %s view. New parameters: %s'%(source, target, view, link_params))
        self.add_link(source, target, view, **link_params)

    def add_new_chain(self, start_sap_id=None, end_sap_id=None,
                      start_sap_opts = dict(), end_sap_opts = dict()):
        """Create and register a new chain with given service attachment points. """
        chain_view = self.config["chain_view"]

        if type(start_sap_opts) is not dict: start_sap_opts = {}
        if type(end_sap_opts) is not dict: end_sap_opts = {}

        start_sap_opts['node_type'] = self.NODE_TYPE_SAP
        end_sap_opts['node_type'] = self.NODE_TYPE_SAP

        start = self.add_node(start_sap_id, chain_view, **start_sap_opts)
        end = self.add_node(end_sap_id, chain_view, **end_sap_opts)

        chain_id = self.chain_counter
        self.chain_counter += 1

        self.chains[chain_id] = {"source": start, "target": end}

        return (chain_id, start, end)

    def get_graph(self, view):
        return self.graphs[view];

    def _next_node_id(self, view):
        node_id = self.status[view].id_counter
        self.status[view].id_counter += 1
        return view + str(node_id)

class Mapping(object):
    logger = logging.getLogger(__name__)

    @staticmethod
    def map(chain_g, res_g, cls_algorithm = DefaultSorter):
        alg = cls_algorithm()
        chain_graph = deepcopy(chain_g)
        res_graph = deepcopy(res_g)

        stnodes = Mapping.get_stnodes(chain_graph)
        stnodes_res =  Mapping.get_stnodes(res_graph)

        for e in stnodes:
            if e not in stnodes_res and e[::-1] not in stnodes_res:
                raise RuntimeError('Missing st node pair %s'%(e,))

        vnf_list = Mapping.get_accessible_vnf_list(stnodes, chain_graph)

        bindings = list()

        for vnf in alg.order_vnf_list(vnf_list, chain_graph):
            host_node = alg.get_node_for_vnf(vnf, chain_graph,res_graph)
            if not host_node:
                Mapping.logger.warn('Can not find host node for %s'%vnf.node_id)
                raise RuntimeError('Can not find host node for %s'%vnf.node_id)
                continue #can not find enough resource. #TODO: now what?

            Mapping.add_vnf_to_host(vnf.node_id, host_node, chain_graph, res_graph)
            bindings.append((vnf.node_id, host_node))

        return bindings

    @staticmethod
    def get_stnodes(g):
        tmp = [node_id for node_id in g.node
               if 'node_type' in g.node[node_id]
               and g.node[node_id]['node_type'] == NetworkGraphManager.NODE_TYPE_SAP]

        l = len(tmp)
        pairs = [(tmp[i], tmp[j]) for i in xrange(0, l) for j in xrange(i+1, l)]

        stnodes = [s for s in pairs if nx.has_path(g, s[0], s[1])]

        return stnodes

    @staticmethod
    def get_accessible_vnf_list(stnodes, g):
        vnf_list = dict()
        for s,t in stnodes:
            node_list = nx.node_connected_component(g, s)
            #if the target is not reachable from the source, the chain
            #is not valid
            if t not in node_list:
                continue

            for node_id in node_list:
                #wee need only VNF nodes
                if g.node[node_id]['node_type'] != NetworkGraphManager.NODE_TYPE_VNF:
                    continue
                vnf_container = Utils.Store()
                vnf_container.node_id = node_id
                vnf_container.node = g.node[node_id]
                vnf_container.s_node = s
                vnf_container.t_node = t
                vnf_list[node_id] = vnf_container

        return vnf_list

    @staticmethod
    def add_vnf_to_host(vnf_node_id, host_node_id, chain_graph, res_graph):

        host_node = res_graph.node[host_node_id]
        vnf_node = chain_graph.node[vnf_node_id]

        res = {key: host_node['res'][key] - vnf_node['req'].get(key, 0) for
               key in host_node['res']}
        host_node['res'].update(res)
        #TODO: update link parameters


class VnfWrapper(Utils.LoggerHelper):
    def __init__(self, node):
        self.node = node
        self.name  = self.node.name
        self.mac = self.node.MAC()
        self.netconf_helper = None
        self.id_to_name = {}

    def start(self, vnf, vnf_options = None):
        self._debug('Start vnf %s on node %s'%(vnf, self.name))
        try:
            agent = self.node.getAgent()
        except AttributeError:
            agent = None
        if agent == None:
            # vnf runs on a mininet host
            self.node.startCmd = vnf.startCmd
            self.node.start()
            # there is no internal vnf_id, no netconf agent
            # so, use pid as a vnf_id
            return self.node.vnfPid

        # If we have NetconfAgent, use vnf_options
        netconf_helper = self._get_netconf_helper(agent)
        initVNF = netconf_helper.rpc("initiateVNF",
                                     vnf_type = vnf_options['function'],
                                     options = {"ip": "127.0.0.1"})
                                     #options = vnf_options['custom_params'])
        vnf_id = initVNF['access_info']['vnf_id']
        vnf_options['vnf_control_port'] = initVNF['access_info']['control_port']
        connectVNF = netconf_helper.rpc("connectVNF",
                                        vnf_id = vnf_id,
                                        vnf_port = "0",
                                        switch_id = self.name)
        netconf_helper.rpc("startVNF",
                           vnf_id = vnf_id)
        # return internal vnf_id administered by netconf agent
        self._info('Started vnf %s by netconf agent on node %s'
                    % (vnf_id, self.name))
        self.id_to_name[vnf_id] = vnf_options['name']
        return vnf_id
        # self._error("can't start VNF on node (%s)" % self.name)

    def _get_netconf_helper(self, agent):
        if self.netconf_helper is None:
            netconf_helper = NetconfHelper(
                server = agent.IP(),
                port = agent.agentPort,
                username = agent.username,
                password = agent.passwd,
                timeout=30)
            # connect to server
            try:
                netconf_helper.connect()
            except AuthenticationError as e:
                self._error('AuthenticationError (%s):%s' % (self.name, e))
                return None
            self.netconf_helper = netconf_helper
        return self.netconf_helper

    def get_vnf_info(self, vnf_opts=None):
        "Return status for 'vnf_opts' or for all vnfs if it is None"
        vnf_info = []
        if self.netconf_helper is not None:
            try:
                vnf_info = self.netconf_helper.rpc("getVNFInfo")
            except RPCError as e:
                vnf_info = {}
            vnf_info = vnf_info.get('initiated_vnfs', [])
            if type(vnf_info) != list:
                vnf_info = [vnf_info]
        if vnf_opts:
            vnf_id = vnf_opts['name']
            vnf_id_netconf = vnf_opts['vnf_id_netconf']
            for info in vnf_info:
                if info.get('vnf_id') != vnf_id_netconf:
                    continue
                return info
            self._error("can't get status of vnf %s on node (%s)" %
                    (vnf_id, self.name))
        else:
            result = {}
            for info in vnf_info:
                name = self.id_to_name.get(info['vnf_id'])
                result[name] = info
            return result

    def stop(self, vnf_opts):
        vnf_id = vnf_opts['name']
        vnf_id_netconf = vnf_opts['vnf_id_netconf']
        if self.netconf_helper is not None:
            try:
                self.netconf_helper.rpc("stopVNF", vnf_id = vnf_id_netconf)
            except RPCError as e:
                self._warn('Failed to stop vnf %s on node %s: %s'
                           % (vnf_id_netconf, self.name, e))
                return
            self._info('Stopped vnf %s by netconf agent on node %s'
                       % (vnf_id_netconf, self.name))
            return
        else:
            # try to stop like a non netconf controlled node
            self.node.stop()


class NodeManagerMininetWrapper:
    def __init__(self):
        self.vnf_wrapper = {}
        self.mn = None

    def set_mininet(self, mininet):
        self.mn = mininet

    def stop(self):
        self.mn = None

    def initialized(self):
        return self.mn is not None

    def get_node(self, node_id):
        return self.get_vnf_wrapper(node_id)

    def get_vnf_wrapper(self, node_id):
        try:
            return self.vnf_wrapper[node_id]
        except KeyError:
            pass

        try:
            node = self.mn.get(node_id)
        except KeyError:
            return None

        self.vnf_wrapper[node_id] = VnfWrapper(node)
        return self.vnf_wrapper[node_id]

    def delete_vnf_wrapper(self, node_id):
        try:
            del self.vnf_wrapper[node_id]
        except KeyError:
            pass


class VNFManager(Utils.LoggerHelper):

    def __init__(self):
        self.vnf_catalog = {}
        self.vnf_to_node = {}
        self.node_manager = None
        self.vnf_options = None

    def set_node_manager(self, node_manager):
        self.node_manager = node_manager

    def set_vnf_catalog(self, catalog):
        self.vnf_catalog = catalog

    def start_vnfs(self, vnf_to_node_list, vnf_options):
        self.vnf_options = deepcopy(vnf_options)
        for vnf_id, node_id in vnf_to_node_list:
            self.start_vnf_on_node(vnf_id, node_id, self.vnf_options[vnf_id]);
            self.vnf_to_node[vnf_id] = node_id
        try:
            self.node_manager.start_posthook()
        except AttributeError:
            #TODO: logmessage
            pass

    def start_vnf_on_node(self, vnf_id, node_id, vnf_options):
        #TODO: change available resources in res_graph

        # here vnf_id is the (hopefully unique) name of the VNF!!!
        self._debug('Start %s vnf on node %s'%(vnf_id, node_id))
        self._debug('Options for this node: %s'%vnf_options)
        # node = self.node_manager.get_node(node_id)
        # vnf = self.create_vnf(vnf_options, node)
        # node.start(vnf, vnf_options)
        vnf_wrapper = self.node_manager.get_vnf_wrapper(node_id)
        vnf = self.create_vnf(vnf_options, vnf_wrapper)
        vnf_id_netconf = vnf_wrapper.start(vnf, vnf_options)
        # None or vnf_id on netconf agent: add to options
        vnf_options['vnf_id_netconf'] = vnf_id_netconf
        self.vnf_to_node[vnf_id] = node_id
        return

    def create_vnf(self, options, host):
        vnf_catalog_entry = self.vnf_catalog[options['function']]
        builder_name = vnf_catalog_entry['builder_class']
        self._debug("Builder class for is %s"%builder_name)
        builder_cls = getattr(VNFBuilders, builder_name, None)
        if not builder_cls:
            raise RuntimeError("Unknown VNF builder %s"%(builder_name))

        builder = builder_cls()
        vnf = builder.create_vnf(options, host)
        self._debug('Finally built vnf: %s'%vnf)
        return vnf

    def get_host_id(self, vnf_id, default=None):
        "Return host where vnf is started"
        if vnf_id in self.vnf_to_node:
            node_id = self.vnf_to_node[vnf_id]
            vnf_wrapper = self.node_manager.get_vnf_wrapper(node_id)
            try:
                if vnf_wrapper.node.getAgent():
                    # this vnf is managed by a netconf agent
                    return vnf_id
            except AttributeError:
                # this vnf runs inside a mininet EE
                return node_id
        else:
            return default

    def get_vnf_info(self, vnf_opts):
        'Get info on given VNF'
        vnf_id = vnf_opts['name']
        node_id = self.vnf_to_node[vnf_id]
        return self.get_vnf_info_on_node(node_id, vnf_opts)

    def get_vnf_info_on_node(self, node_id, vnf_opts=None):
        if not self.node_manager.initialized():
            return {}
        vnf_wrapper = self.node_manager.get_vnf_wrapper(node_id)
        if not vnf_wrapper:
            return {}

        return vnf_wrapper.get_vnf_info(vnf_opts)

    def stop_vnf(self, vnf_id):
        'Stop VNF via netconf agent'
        #TODO: indicate resource release (event?)

        node_id = self.vnf_to_node.get(vnf_id)
        if not node_id:
            # this vnf doesn't run anyhere
            return
        vnf_opts = self.vnf_options[vnf_id]
        vnf_id = vnf_opts['name']
        vnf_wrapper = self.node_manager.get_vnf_wrapper(node_id)
        vnf_wrapper.stop(vnf_opts)

    def stop_vnfs(self):
        for vnf_id in self.vnf_to_node.keys():
            self.stop_vnf(vnf_id)

    def remove_vnf(self, vnf_id):
        'Remove a vnf from our DB. (Call this when the VNF has been stopped.)'
        node_id = self.vnf_to_node.get(vnf_id)
        vnf_opts = self.vnf_options[vnf_id]
        del self.vnf_to_node[vnf_id]
        del self.vnf_options[vnf_id]

    def start_clicky(self, vnf_id):
        node_id = self.vnf_to_node[vnf_id]
        vnf_wrapper = self.node_manager.get_vnf_wrapper(node_id)
        mininet_node = vnf_wrapper.node
        opts = self.vnf_options.get(vnf_id)
        if not opts:
            self._warn("can't start clicky for %s" % vnf_id)
            return []

        port = opts.get('vnf_control_port')
        return clickgui.makeClicky( mininet_node, control_port=port )


#Node interface
class Node(object):
    def start_vnf(self, vnf):
        raise NotImplementedError()

#NodeManager interface
class NodeManager(object):

    def get_node(self, node_id):
        raise NotImplementedError()

    def start_posthook(self):
        raise NotImplementedError()

class DefaultRouteAlgorithm(object):

    def __init__(self):
        self.g = nx.Graph()
        self.valid_type = (NetworkGraphManager.NODE_TYPE_SAP,
                           NetworkGraphManager.NODE_TYPE_HOST,
                           NetworkGraphManager.NODE_TYPE_VNF,
                           NetworkGraphManager.NODE_TYPE_SWITCH)

    def graph(self, node_links_data):
        self.g = json_graph.node_link_graph(node_links_data)
        remove = list()
        for _id in self.g.node:
            if self.g.node[_id]["node_type"] not in self.valid_type:
                remove.append(_id)
        self.g.remove_nodes_from(remove)

    def shortest_path(self, source, target):
        return nx.shortest_path(self.g, source, target, weight = "weight")

    def chain_hops(self, s, t):
        line = self.shortest_path(s, t)
        return zip(line[0:], line[1:])

    def res_hops(self, s, t):
        try:
            line = self.shortest_path(s, t)
            return zip(line[0:], line[1:])
        except (nx.NetworkXNoPath, KeyError):
            return None

class RouteManager(Utils.GenericEventNotifyer, Utils.LoggerHelper):

    def __init__(self, vnf_manager,
                 chain_route_search_algorithm = DefaultRouteAlgorithm,
                 res_route_search_algorithm = DefaultRouteAlgorithm):
        Utils.GenericEventNotifyer.__init__(self)
        self.route_id = 0
        self.dpids = dict()
        self.port_map = dict()
        self.routes = dict()
        self.vnf_manager = vnf_manager
        self.chain_route_search = chain_route_search_algorithm()
        self.res_route_search = res_route_search_algorithm()
        boot.core.callLater(boot.core.TrafficSteering.addListeners, self)

    def get_route_ids(self):
        return self.routes.keys()

    def get_vnfs_in_route(self, route_id):
        route = self.routes.get(route_id, {})
        vnf_ids = set()
        for s,t in route.get('chain'):
            vnf_ids.add(s)
            vnf_ids.add(t)
        return list(vnf_ids)

    def install_routes(self, chain_graph, res_graph):
        stpoints = Mapping.get_stnodes(chain_graph)

        for s,t in stpoints:
            self._install_one_route(chain_graph, res_graph, s, t)
            self._install_one_route(chain_graph, res_graph, t, s, True)

    def _install_one_route(self, chain_graph, res_graph, s, t, backroute=False):
        self._debug('Install route between %s - %s (backroute=%s)' %
                        (s, t, backroute))

        route_id = self.next_route_id()
        self.routes[route_id] = { 'chain': [],
                                  'res': [],
                                  'status': RouteChanged.PENDING,
                                  'res_graph': res_graph,
                                  }

        if backroute:
            #route_search = DefaultRouteAlgorithm()
            #route_search.graph(json_graph.node_link_data(res_graph))

            # send backward traffic directly to the source:
            chain_hops = [(s, t)]
        else:
            route_search = self.chain_route_search
            route_search.graph(json_graph.node_link_data(chain_graph))
            chain_hops = route_search.chain_hops(s, t)

        self.routes[route_id]['chain'] = chain_hops
        self._fire_route_state_change(None, route_id)
        self.install_pending_routes(res_graph)

    def install_pending_routes(self, res_graph):
        for route_id, r in self.routes.iteritems():
            if r['status'] == RouteChanged.PENDING:
                self._install_one_pending_route(route_id, res_graph)

    def _install_one_pending_route(self, route_id, res_graph):
        self.res_route_search.graph(json_graph.node_link_data(res_graph))

        path_stream = []
        self.routes[route_id]['res'] = []
        chain_hops = self.routes[route_id]['chain']
        for u, v in chain_hops:
            self._debug('\tNext hop in chain view: %s - %s'%(u, v))
            u_host = self.vnf_manager.get_host_id(u, u)
            v_host = self.vnf_manager.get_host_id(v, v)
            self._debug('\tTranslated to %s - %s'%(u_host, v_host))
            res_hops = self.res_route_search.res_hops(u_host,v_host)
            if not res_hops:
                # route not (yet) available:
                self._debug('no route between: %s-%s' % (u_host, v_host))
                return
            for i,j in res_hops:
                self._debug('\t\tNext hop in res view: %s - %s'%(i,j))
                self.routes[route_id]['res'].append((i,j))
                path_stream.append(i)
                last = j
        path_stream.append(last)

        self.routes[route_id]['status'] = RouteChanged.STARTING
        self._fire_route_state_change(None, route_id)

        route_fwd = []
        for idx, e in enumerate(path_stream):
            if e in self.dpids:
                dpid = self.dpids[e]
                if dpid < 0:
                    continue
                source_port = self.port_map[e][path_stream[idx-1]]
                destination_port = self.port_map[e][path_stream[idx+1]]
                self._debug('Route hop:(dpid> in-p -- out-p) %s>%s -- %s'
                           %(dpid, source_port, destination_port))
                r = RouteHop(dpid, source_port, destination_port)
                route_fwd.append(r)

        core.core.callLater(core.core.TrafficSteering.add_route,
                            route_id, route_fwd)

    def remove_route(self, route_id):
        core.core.callLater(core.core.TrafficSteering.remove_route,
                            route_id)

    def _handle_dpid_update(self, event):
        self.dpids = event.dpids

    def _handle_port_map_update(self, event):
        self.port_map = event.port_map

    def _handle_vnf_update(self, event):
        if event.status == 'stopped':
            self.vnf_manager.remove_vnf(event.name)

    def _handle_RouteChanged (self, event):
        if event.id in self.routes:
            self.routes[event.id]['status'] = event.status
        self._fire_route_state_change(event)

    def _fire_route_state_change(self, event, id=None):
        if not event:
            status = self.routes[id]['status']
            event = RouteChanged(id, status)
        event.route_map = self.routes[event.id]
        if event.status == RouteChanged.REMOVED:
            del self.routes[event.id]
        self.fire('route_state_change', event)

    def next_route_id(self):
        self.route_id += 1
        return self.route_id


class Orchestrator(object):
    ""
    def __init__(self, network_manager, route_manager):
        self.network_manager = network_manager
        self.rm = route_manager

    def start(self, nf_g, phy_g):
        # TODO: instead of phy_g, rely on NetworkManager, or simple_topology

        if nf_g.number_of_nodes() < 1 or \
           phy_g.number_of_nodes() < 1 or\
           not self.network_manager.network_alive():
            return []

        vnf_to_host_list = Mapping.map(nf_g, phy_g, DefaultSorter)

        vnf_options = nf_g.node
        vnf_manager = self.network_manager.vnf_manager
        vnf_manager.set_vnf_catalog(Catalog().get_db())
        vnf_manager.start_vnfs(vnf_to_host_list, vnf_options)
        self.rm.install_routes(nf_g, phy_g)

        return vnf_to_host_list

    def stop_service_graphs(self):
        "Stop every service graph."
        vnf_manager = self.network_manager.vnf_manager

        for route_id in self.rm.get_route_ids():
            vnfs = self.rm.get_vnfs_in_route(route_id)
            self.rm.remove_route(route_id)
            for vnf_name in vnfs:
                vnf_manager.stop_vnf(vnf_name)
