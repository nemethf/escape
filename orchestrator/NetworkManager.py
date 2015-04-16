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

"""
Created on Jul 18, 2014

@author: csoma, czentye
"""
import time
import threading
import copy
from subprocess import call
import networkx as nx
from tkMessageBox import showerror

from Utils import Store, GenericEventNotifyer, LoggerHelper
import pox.core
from mininet.cli import CLI
from mininet.net import Mininet, MininetWithControlNet
from mininet.node import Controller, RemoteSwitch
from mininet.link import Intf, Link
import mininet.clean
from pox.lib.revent.revent import EventMixin, Event

from CustomNetworkElements import InbandController, customOvs, CustomUserSwitch
from mininet.moduledeps import moduleDeps
from mininet.util import quietRun
from mininet.cli import CLI
from mininet.net import MininetWithControlNet
from mininet.node import Controller, RemoteController, OVSController, EE, RemoteSwitch, IVSSwitch, CPULimitedHost, Host
from mininet.link import TCLink, Intf, Link

# Constants for NetworkX conversation
NODE_TYPE = {'CONTROLLER': 'C',
             'NODE': 'HOST',
             'SAP': 'SAP',
             'SWITCH': 'SW'}
LINK_TYPE = {'CONTROL': 'control',
             'DATA': 'data'}

class LinkChange(Event):
    """
    Event representing a changes link state
    """
    def __init__(self, node1, node2, intf1, intf2, delete=False):
        Event.__init__(self)
        self.node1 = node1
        self.node2 = node2
        self.intf1 = intf1
        self.intf2 = intf2
        self.delete = delete

class NodeChange(Event):
    """
    Send this event if something changed
    in node parameters after latest notification
    """
    TYPE_DUMMY = -1
    TYPE_SWITCH = 1
    TYPE_EE = 2
    TYPE_SAP = 3
    TYPE_CONTROLLER = 3

    def __init__(self, nc_type, **kw):
        """
        event structure:
        @self.type - node type (not used yed)
        @self.intf - interface list
         e.g:
        {'sap1-eth0': {'ip': '10.0.0.6',
                       'mac': '00:00:00:00:00:06',
                       'port': 0}
                       }
         {'lo': {'ip': '127.0.0.1',
                 'mac': None,
                 'port': 0
                 },
          's3-eth4': {'ip': None,
                      'mac': '32:13:3f:c1:7c:e4',
                      'port': 4
                      },
          ...
          }
        @self.name - name of the node in mininet
        @self.dpid - dpid number if type = TYPE_SWITCH, None otherwise
        """
        Event.__init__(self)
        self.type = nc_type

        self.intf = kw['intf']
        self.name = kw['name']
        self.dpid = kw.get('dpid', None)

class NetworkManager(EventMixin):
    """
    Very basic superclass
    """
    DOWN = 0
    UP = 1
    SCANNED = 2
    STARTING = 3
    STOPPING = 4
    _eventMixin_events = {LinkChange, NodeChange}

class NetworkManagerMininet(NetworkManager,
                            GenericEventNotifyer,
                            LoggerHelper):
    __shared_state = {}

    def __init__(self):
        'lazy init'
        self.__dict__ = self.__shared_state
        if self.__dict__:
            # already initialized
            return

        GenericEventNotifyer.__init__(self)
        self.net = None
        # Initial topo to create Mininet topology
        self.initial_topo = None
        # Network state
        self.state = NetworkManager.DOWN
        self.port_map = {}
        self.dpid = {}
        # Running topo to manage/store running topo obtained from Mininet - dummy object
        self.network = Store()
        # Active link list
        self.network.links = {}
        # Active node list
        self.network.nodes = {}
        # Queue for parallel event processing 
        self.of_event_queue = []
        # Timer daemon process for periodic polling
        self.process = None
        self.vnf_manager = None
        self.last_status_poll = 0
        pox.core.core.listen_to_dependencies(self)
        # Start periodic scan
        self.periodic_scan()

    #########
    ### Mininet topology compilation
    #########
    
    def build_topo_network(self, network_topo, appPrefs):
        """
        Filling Mininet "topo" with app specific data
        network_topo - Topology object need to update
        appPrefs - global startup parameters
        
        No return
        """
        dpctl = None if not appPrefs['dpctl'] else int(appPrefs['dpctl'])
        #dpctl = int(appPrefs['dpctl']) if 'dpctl' in appPrefs else None
        network_topo['netopts'].update({'listenPort': dpctl,
                                        'topo': None,
                                        'build': False,
                                        'ipBase': appPrefs['ipBase'],
                                        'autoSetMacs': True,
                                        'autoStaticArp': True})
        self._debug('Add global parameters: %s' % network_topo['netopts'])

    def build_topo_switch(self, network_topo, name, opts, appPrefs):
        """
        Build switch object with given name and "opts" params
        network_topo - Topology object need to update
        name - switch name
        opts - switch instance params
        appPrefs - global startup parameters
        
        No return
        """
        required_keys = {'switchType'}
        if not opts.viewkeys() & required_keys:
            raise KeyError('Required argument is missing!\nCheck: ' + repr(required_keys))
        switch = dict()
        switchParms = {'name': name}
        if 'dpctl' in opts:
            switchParms['listenPort'] = int(opts['dpctl'])
        if 'dpid' in opts:
            switchParms['dpid'] = opts['dpid']
        # Get switch type or default
        if opts['switchType'] == 'default':
            sw_type = appPrefs['switchType']
        else:
            sw_type = opts['switchType']
        # Get the correct switch class
        if sw_type == 'ivs':
            switchParms['cls'] = IVSSwitch
        elif sw_type == 'user':
            switchParms['cls'] = CustomUserSwitch
        elif sw_type == 'userns':
            switchParms['inNamespace'] = True
            switchParms['cls'] = CustomUserSwitch
        else:
            switchParms['cls'] = customOvs
            switch['openflowver'] = appPrefs['openFlowVersions']
        switch['controllers'] = opts.get('controllers', None)
        switch['netflow'] = opts.get('netflow', None)
        switch['sflow'] = opts.get('sflow', None)
        # Are these ifs important or switch instances can contain empty ip, extintf attributes?
        # Attach external interfaces
        if 'externalInterfaces' in opts:
            switch['extintf'] = opts['externalInterfaces']
        if 'ip' in opts:
            switch['ip'] = opts['switchIP']
        # Add new switch param and switch
        switch['params'] = switchParms
        network_topo['switches'][opts['_id']] = switch
        self._debug('Add %s Switch to mininet topo with parameters %s' % (name, network_topo['switches'][opts['_id']]))
        
    def build_topo_ee(self, network_topo, name, opts):
        """
        Build VNF Container object with given name and "opts" params
        network_topo - Topology object need to update
        name - Container name
        opts - Container instance params
        
        No return
        """
        settings = {}
        ip = opts.get('ip', None)
        if ip: settings['ip'] = ip

        defaultRoute = opts.get('defaultRoute', None)
        if defaultRoute: settings['defaultRoute'] = 'via ' + defaultRoute

        # Create the correct host class
        hostCls = EE
        params = {'name': name,
                  'cls': hostCls,
                  'cpu': opts['res']['cpu'],
                  'mem': opts['res']['mem'],
                  'ee_type': opts.get('ee_type', 'static'),
                  }
        for o in ['remote_dpid', 'remote_port', 'remote_conf_ip',
                  'remote_netconf_port', 'netconf_username',
                  'netconf_passwd', 'local_intf_name']:
            params[o] = opts.get(o)

        params.update(settings)
        network_topo['ee'][opts['_id']]={'params': params}

        if False:
            # Set the CPULimitedHost specific options
            if 'cores' in opts:
                network_topo['ee'][opts['_id']]['cores'] = opts['cores']
            if 'cpu' in opts:
                network_topo['ee'][opts['_id']]['frac']={'f':opts['res']['cpu'],
                                                         'sched':opts['sched']
                                                         }

        # Attach external interfaces
        if 'externalInterfaces' in opts:
            network_topo['ee'][opts['_id']]['extintf'] = opts['externalInterfaces']

        vlanif = opts.get('vlanInterfaces', None)
        if vlanif:
            self._debug('Checking that OS is VLAN prepared')
            self.pathCheck('vconfig', moduleName='vlan package')
            moduleDeps( add='8021q' )
            network_topo['ee'][opts['_id']]['vlanif'] = vlanif
            
        self._debug("Add %s EE to mininet topo with parameters %s" % (name, network_topo['ee'][opts['_id']]))

    def pathCheck( self, *args, **kwargs ):
        """Make sure each program in *args can be found in $PATH."""
        moduleName = kwargs.get( 'moduleName', 'it' )
        for arg in args:
            if not quietRun( 'which ' + arg ):
                showerror(title="Error",
                      message= 'Cannot find required executable %s.\n' % arg +
                       'Please make sure that %s is installed ' % moduleName +
                       'and available in your $PATH.' )

    def build_topo_controller(self, network_topo, name, opts):
        """
        Build Controller object with given name and "opts" params
        network_topo - Topology object need to update
        name - Controller name
        opts - Controller instance params
        
        No return
        """
        # Get controller info from panel
        controllerType = opts['controllerType']

        # Make controller
        self._info('*** Getting controller selection: %s' % controllerType)

        if controllerType == 'remote':
            c = RemoteController
        elif controllerType == 'inband':
            c = InbandController
        elif controllerType == 'ovsc':
            c = OVSController
        else:
            c = Controller
        params = {'name': name,
                  'ip': opts['remoteIP'],
                  'port': opts['remotePort'],
                  'controller': c
                  }
        network_topo['controllers'][opts['_id']] = {'params': params}
        self._debug("Add %s Controller(s) to mininet topo with parameters %s" % (name, network_topo['controllers'][opts['_id']]))

    def build_topo_sap(self, network_topo, name, opts):
        settings = {}
        ip = opts.get('ip', None)
        if ip: settings['ip'] = ip
                    # else:
                        # nodeNum = canvas.startpointOpts[name]['nodeNum']
                        # settings['nodeNum']= nodeNum
                        # ipBaseNum, prefixLen = netParse( self.appPrefs['ipBase'] )
                        # settings['ipBaseNum'] = ipBaseNum
                        # settings['prefixLen'] = prefixLen
                        # ip = ipAdd(i=nodeNum, prefixLen=prefixLen, ipBaseNum=ipBaseNum)

        defaultRoute = opts.get('defaultRoute', None)
        if defaultRoute: settings['defaultRoute'] = 'via ' + defaultRoute

        # Create the correct host class        
        hostCls = Host
        if 'cores' in opts or 'cpu' in opts:
            hostCls=CPULimitedHost

        params = {'name': name,
                  'cls': hostCls
                  }
        params.update(settings)
        network_topo['saps'][opts['_id']]={'params': params}

                    # Set the CPULimitedHost specific options
        if 'cores' in opts:
            network_topo['saps'][opts['_id']]['cores'] = opts['cores']
        if 'cpu' in opts:
            network_topo['saps'][opts['_id']].update({'f':opts['res']['cpu'],
                                                     'sched':opts['sched']
                                                     })

                    # Attach external interfaces
        if 'externalInterfaces' in opts:
            network_topo['saps'][opts['_id']]['extintf'] = \
            opts['externalInterfaces']

        vlanif = opts.get('vlanInterfaces', None)
        if vlanif:
            pass
                            # self._debug('Checking that OS is VLAN prepared')
                            # self.pathCheck('vconfig', moduleName='vlan package')
                            # moduleDeps( add='8021q' )
        self._debug("Add %s SAP to mininet topo with parameters %s" % (name, network_topo['saps'][opts['_id']]))

    def build_topo_links(self, network_topo, phy_g):     
        for node1, node2, params in list(phy_g.edges_iter(data=True)):
            if params.get('type', None) == 'data':
                network_topo['links'][(node1, node2)] = {'node1': node1,
                                                         'node2': node2,
                                                         'cls': TCLink}
                if 'delay' in params:
                    network_topo['links'][(node1, node2)]['delay'] = params.get('delay', 5)
                if 'bw' in params:
                    network_topo['links'][(node1, node2)]['bw'] = params['bw']
                self._debug("Create link between %s : %s with parameters %s" % (node1, node2, network_topo['links'][(node1, node2)]))
                
    # TODO: don't use appPrefs and canvas, references and bindings to GUI should be removed
    # check imports to eliminate unnecessary ones
    def build_topo(self, phy_g, appPrefs):
        """
        Generate and set mininet topo
        
        No return
        """
        from Utils import dump
        #dump(phy_g)
        self.initial_topo = self.generate_topo(phy_g, appPrefs)
        
    def generate_topo(self, phy_g, appPrefs):
        """
        Build the topology according to the GUI widget params
        appPrefs - global params: ipBase, switchType, openFlowVersions
        Return: topo object
        """
        self._info("*** Build network based on our topology.")
        # Empty topo
        network_topo = { 'netopts': dict(),
                         'ee': dict(),
                         'saps': dict(),
                         'switches': dict(),
                         'controllers': dict(),
                         'links': dict()
                        }
        # Set global params
        self.build_topo_network(network_topo, appPrefs)
        
        # Make nodes
        self._info("*** Getting Hosts and Switches.")
        for node in phy_g.nodes():
            if phy_g.node[node]['node_type'] == NODE_TYPE['SWITCH']:
                # Adding specific switch object to "topo"
                self.build_topo_switch(network_topo, node, phy_g.node[node], appPrefs)
                # TODO: Need to handle 'LegacySwitch' ???
                    # elif 'LegacySwitch' in tags:
                        # opts = canvas.switchOpts[name]
                        # params = {'params':{'name': name,
                                            # 'cls': LegacySwitch}
                                  # }
                        # # Adding specific switch object to "topo"
                        # network_topo['switches'][opts['_id']] = params
            elif phy_g.node[node]['node_type'] == NODE_TYPE['NODE']:
                # Adding specific EE object to "topo"
                self.build_topo_ee(network_topo, node, phy_g.node[node])
            elif phy_g.node[node]['node_type'] == NODE_TYPE['CONTROLLER']:
                # Adding specific controller object to "topo"
                self.build_topo_controller(network_topo, node, phy_g.node[node])
                # TODO: Need to handle 'LegacyRouter' ???
                    # elif 'LegacyRouter' in tags:
                        # opts = canvas.switchOpts[name]
                        # params = {'params':{'name': name,
                                            # 'cls': LegacyRouter}
                                  # }
                        # # Adding specific router object to "topo"
                        # network_topo['hosts'][opts['_id']] = params
            elif phy_g.node[node]['node_type'] == NODE_TYPE['SAP']:
                # Adding specific SAP object to "topo"
                self.build_topo_sap(network_topo, node, phy_g.node[node])
            else:
                raise TypeError('Cannot create mystery node: ' + node)
            
        # Adding the links
        self._info("*** Getting Links.")
        self.build_topo_links(network_topo, phy_g)
        
        return network_topo
    
    #########
    ### Mininet topology creation
    #########
    
    # Use this function instead of direct access to initial_topo
    def get_initial_topology(self):
        """
        General function to return the observed topology in the NetworkX format
        """
        return self._convert_to_NetworkX_format()

    def _convert_to_NetworkX_format(self):
        """
        Convert the "topo" dictionary to NetworkX format for Orchestration module
        Keep only the relevant node information
        Return: graph - networkx.classes.graph.Graph
        @author: czentye
        """
        # Create empty graph
        graph = nx.Graph()
        # Return if topo is not set
        if not self.initial_topo:
            return graph
        from Utils import dump
        #dump(self.initial_topo, 'NetMen initial_topo')
        # Convert "controllers" to node
        controllers = self.initial_topo['controllers']
        for c in controllers:
            node_name = controllers[c]['params']['name']
            graph.add_node(node_name)
            graph.node[node_name]['_id'] = c
            graph.node[node_name]['node_type'] = NODE_TYPE['CONTROLLER']
            graph.node[node_name]['hostname'] = node_name

            graph.node[node_name]['controllerType'] = None   #TODO cut from controllers[c]['params']['controller']
            graph.node[node_name]['canvas_id'] = None

            graph.node[node_name]['remoteIP'] = controllers[c]['params']['ip']
            graph.node[node_name]['remotePort'] = controllers[c]['params']['port']

        # Convert "ee" to node
        ee = self.initial_topo['ee']
        for container in ee:
            node_name = ee[container]['params']['name']
            graph.add_node(node_name)
            graph.node[node_name]['_id'] = container
            graph.node[node_name]['node_type'] = NODE_TYPE['NODE']
            graph.node[node_name]['hostname'] = node_name

            graph.node[node_name]['nodeNum'] = None
            graph.node[node_name]['canvas_id'] = None

            # graph.node[node_name]['ee_type'] = ee[container]['params']['ee_type']
            # graph.node[node_name]['cpu'] = ee[container]['params']['cpu']
            # graph.node[node_name]['mem'] = ee[container]['params']['mem']
            # Duplicated data, SHOULD be removed !!!
            graph.node[node_name]['res'] = {'cpu': ee[container]['params']['cpu'], 'mem': ee[container]['params']['mem']}

        # Convert "saps" to node
        saps = self.initial_topo['saps']
        for sap in saps:
            node_name = saps[sap]['params']['name']
            graph.add_node(node_name)
            graph.node[node_name]['_id'] = sap
            graph.node[node_name]['node_type'] = NODE_TYPE['SAP']
            graph.node[node_name]['name'] = node_name

            graph.node[node_name]['canvas_id'] = None
            graph.node[node_name]['nodeNum'] = None

        # Convert "switches" to node
        switches = self.initial_topo['switches']
        for switch in switches:
            node_name = switches[switch]['params']['name']
            graph.add_node(node_name)
            graph.node[node_name]['_id'] = switch
            graph.node[node_name]['node_type'] = NODE_TYPE['SWITCH']
            graph.node[node_name]['hostname'] = node_name

            graph.node[node_name]['canvas_id'] = None
            graph.node[node_name]['nodeNum'] = None

            graph.node[node_name]['controllers'] = switches[switch]['controllers']
            graph.node[node_name]['netflow'] = switches[switch]['netflow']
            graph.node[node_name]['sflow'] = switches[switch]['sflow']
            #graph.node[node_name]['switchIP'] = ''
            graph.node[node_name]['switchType'] = None   #TODO cut from switches[switch]['params']['cls']

        # Convert "links" to edges
        links = self.initial_topo['links']
        for node1, node2 in links:
            options = {'weight': 1}
            if graph.node[node1]['node_type'] == 'C' or graph.node[node2]['node_type'] == 'C':
                # Control links are missing from topo -> this branch is useless
                options['type'] = LINK_TYPE['CONTROL']
            else:
                if 'bw' in links[(node1, node2)]:
                    options['bw'] = links[(node1, node2)]['bw']
                options['type'] = LINK_TYPE['DATA']
                if 'delay' in links[(node1, node2)]:
                    options['delay'] = links[(node1, node2)].get('delay', 5)
            graph.add_edge(node1, node2, attr_dict=options)

        # Adding control channel links
        # TODO improve if there is multiple controller
        for node in self.initial_topo['switches']:
            graph.add_edge(self.initial_topo['switches'][node]['controllers'][0], node, attr_dict={'type': LINK_TYPE['CONTROL'], 'weight': 1})
        return graph

    def _start_mininet(self, opts=None):
        if not opts:
            opts = {}
        self._info("***Starting mininet***")
        opts['controller'] = Controller
        opts['autoSetMacs'] = True
        self.net = MininetWithControlNet(**opts)

    def _create_ee(self, ees):
        self._info('**** Create %d execution environment(s)' % len(ees))
        for id, ee in ees.iteritems():
            params = ee['params']
            name = params['name']
            self._debug('\tCreate %s EE with params %s' % (name, ee))
            if params['ee_type'] == 'netconf':
                sw = self.net.addSwitch(name)
                agt = self.net.addAgent('agt_' + name)
                agt.setSwitch(sw)
                continue
            elif params['ee_type'] == 'remote':
                p = copy.deepcopy(params)
                p['cls'] = None
                p['inNamespace'] = False
                p['dpid'] = p['remote_dpid']
                p['username'] = p['netconf_username']
                p['passwd'] = p['netconf_passwd']
                p['conf_ip'] = p['remote_conf_ip']
                p['agentPort'] = p['remote_netconf_port']
                del p['name']
                sw = self.net.addRemoteSwitch(name, **p)
                agt = self.net.addAgent('agt_' + name, **p)
                agt.setSwitch(sw)
                continue
            else:
                # params['ee_type'] == 'static':
                # normal case
                h = self.net.addEE(**params)
                if 'cores' in ee:
                    h.setCPUs(**ee['cores'])
                if 'frac' in ee:
                    h.setCPUFrac(**ee['frac'])
                if 'vlanif' in ee:
                    for vif in ee['vlaninf']:
                        # TODO: In miniedit it was after self.net.build()
                        h.cmdPrint('vconfig add '+name+'-eth0 '+vif[1])
                        h.cmdPrint('ifconfig '+name+'-eth0.'+vif[1]+' '+vif[0])

    def _create_switches(self, switches):
        self._info('**** Create %d switch(es)'%len(switches))
        for id, switch in switches.iteritems():
            self._debug('\tCreate %s switch with params %s' % (switch['params']['name'], switch))
            sw = self.net.addSwitch(**switch['params'])
            if 'openflowver' in switch:
                sw.setOpenFlowVersion(switch['openflowver'])
            if 'ip' in switch:
                sw.setSwitchIP(switch['ip'])

    def _create_controllers(self, controllers):
        self._info('**** Create %d controller(s)'%len(controllers))
        for id, controller in controllers.iteritems():
            self._debug('\tCreate %s controller with params %s' % (controller['params']['name'], controller))
            self.net.addController(**controller['params'])

    def _create_saps(self, saps):
        self._info('**** Create %d SAP(s)'%len(saps))
        for id, sap in saps.iteritems():
            self._debug('\tCreate %s SAP with params %s' % (sap['params']['name'], sap))
            self.net.addHost(**sap['params'])

    def _create_links(self, links):

        def is_remote(node):
            return isinstance(node, RemoteSwitch)

        def is_local(node):
            return not is_remote(node)

        self._info('**** Create %d link(s)' % len(links))
        for id, link in links.iteritems():
            self._debug('\tCreate link %s with params: %s' % (id, link))
            node1 = self.net.get(link['node1'])
            node2 = self.net.get(link['node2'])
            name_to_node = {'node1': node1, 'node2': node2}
            link.update(name_to_node)

            remote = filter(is_remote, [node1, node2])
            local = filter(is_local, [node1, node2])
            if not remote:
                self.net.addLink(**link)
            else:
                sw = local[0]
                r = remote[0]
                intfName = r.params['local_intf_name']
                r_mac = None # unknown, r.params['remote_mac']
                r_port = r.params['remote_port']
                self._debug('\tadd hw interface (%s) to node (%s)' % (intfName, sw.name))

                # This hack avoids calling __init__ which always makeIntfPair()
                link = Link.__new__(Link)
                i1 = Intf(intfName, node=sw, link=link)
                i2 = Intf(intfName, node=r, mac=r_mac, port=r_port, link=link)
                i2.mac = r_mac # mn runs 'ifconfig', which resets mac to None
                #
                link.intf1, link.intf2 = i1, i2

    def _start_controllers(self):
        self._info('**** Start controller(s)')
        for controller in self.net.controllers:
            controller.start()

    def _start_switches(self, switches):
        for id, switch in switches.iteritems():
            controllers = [] #with legacySwitch there is no controller in miniedit
            if switch['controllers']:
                controllers.append(self.net.get(*switch['controllers']))
            self.net.get(switch['params']['name']).start(controllers)

    def start_topo(self, **kwargs):
        """
        Start the physical topology (using Mininet)
        topo - Set and use this topology
        nflow - 
        sflow - 
        startcli - 
        
        No return
        """
        
        self.change_network_state(NetworkManager.STARTING)
        # Save given topo (created by MiniEdit)
        if 'topo' in kwargs:
            self.initial_topo = kwargs['topo']

        if self._is_initial_topo_empty():
            raise AttributeError("Initial topology is missing!!!")

        self._start_mininet(self.initial_topo['netopts'])
        self._create_ee(self.initial_topo['ee'])
        self._create_switches(self.initial_topo['switches'])
        self._create_controllers(self.initial_topo['controllers'])
        self._create_saps(self.initial_topo['saps'])
        self._create_links(self.initial_topo['links'])

        self.net.build()
        self.net.start()

        if 'nflow' in kwargs and kwargs['nflow'].get('nflowTarget'):
            self.start_nflow(kwargs['nflow']['nflowTarget'],
                             kwargs['nflow']['nflowTimeout'],
                             kwargs['nflow']['nflowAddId'])
        if 'sflow' in kwargs and kwargs['sflow'].get('sflowTarget'):
            self.start_sflow(kwargs['sflow']['sflowTarget'],
                             kwargs['sflow']['sflowHeader'],
                             kwargs['sflow']['sflowSampling'],
                             kwargs['sflow']['sflowPolling'])
        if 'startcli' in kwargs and kwargs['startcli'] == '1':
            self.start_cli()

        self.change_network_state(NetworkManager.UP)

    def _is_initial_topo_empty(self):
        return self.initial_topo is None or ('ee' in self.initial_topo and 'saps' in self.initial_topo and 'switches' in self.initial_topo and 'controller' in self.initial_topo)
        
    def stop_network(self):
        self.change_network_state(NetworkManager.STOPPING)
        if self.net is not None:
            self.net.stop()
        self.net = None
        self.initial_topo = None
        self.network.links = {}
        self.network.nodes = {}
        self.dpid = {}
        self.port_map = {}
        # self._debug('Cleaning up Mininet...')
        # mininet.clean.cleanup()
        # time.sleep(4)
        self.change_network_state(NetworkManager.DOWN)

    def network_alive(self):
        return self.state in [NetworkManager.UP]

    def start_sflow(self, target, header, sampling, polling):
        sflowEnabled = False
        sflowSwitches = ''
        for switch in self.initial_topo['switches'].itervalues():
            name = switch['params']['name']
            if switch.get('sflow', None) == '1':
                self._info('%s has sflow enabled' % name)
                sflowSwitches += ' -- set Bridge '+name+' sflow=@MiniEditSF'
                sflowEnabled=True

        if sflowEnabled:
            sflowCmd = 'ovs-vsctl -- --id=@MiniEditSF create sFlow '\
                       'target=\\\"'+target+'\\\" '\
                       'header='+header+' '+ \
                       'sampling='+sampling+' '+\
                       'polling='+polling
            self._debug('sFlow command: cmd = %s%s' % (sflowCmd,sflowSwitches))
            call(sflowCmd+sflowSwitches, shell=True)

        else:
            self._info('No switches with sflow')

    def start_nflow(self, nflowTarget, nflowTimeout, nflowAddId):
        nflowSwitches = ''
        nflowEnabled = False
        for switch in self.initial_topo['switches'].itervalues():
            name = switch['params']['name']
            if switch.get('netflow', None) == '1':
                self._info('%s has Netflow enabled'% name)
                nflowSwitches += ' -- set Bridge '+name+' netflow=@MiniEditNF'
                nflowEnabled=True

        if nflowEnabled:
            nflowCmd = 'ovs-vsctl -- --id=@MiniEditNF create NetFlow '\
                       'target=\\\"'+nflowTarget+'\\\" '\
                       'active-timeout='+nflowTimeout

            if nflowAddId == 1:
                nflowCmd += ' add_id_to_interface=true'
            else:
                nflowCmd += ' add_id_to_interface=false'

            self._debug('nFlowcmd = %s'%(nflowCmd+nflowSwitches))
            call(nflowCmd+nflowSwitches, shell=True)

        else:
            self._info('No switches with Netflow')

    def start_cli(self):
        CLI(self.net)

    def start_clicky(self, vnf_name):
        instances = self.vnf_manager.start_clicky(vnf_name)
        self.net.clickys += instances
        # self._debug('CLICKY: %s' % instances)

    #########
    ### Scan the Mininet network and updating the running topology
    #########
    
    def periodic_scan(self, wait = 1):
        """Scan the Mininet topo and recall itself after a period of time (wait)"""
        self.scan_network()

        self.process = threading.Timer(wait, self.periodic_scan)
        self.process.daemon = True
        self.process.start()

    def scan_network(self, forced = False):
        self.process_event_queue()
        if not self.net or self.state == NetworkManager.STOPPING:
            return
        self.poll_netconf_agents(forced)

        checked = []
        # net -> Mininet network representation
        for name, node in self.net.items():
            checked.append(name)
            if not self.found_node(node):
                return

        deleted = []
        for name, opts in self.network.nodes.iteritems():
            if opts.get('parent'):
                # netconf-controlled vnf node, mininet doesn't know about it
                continue
            if name not in checked:
                deleted.append(name)
        if self.state != NetworkManager.STARTING:
            for node_name in deleted:
                self._debug('remove node (%s) from network table' % node_name)
                del self.network.nodes[node_name]
                # TODO: send event

        deleted = []
        for link_id, link in self.network.links.iteritems():
            node_names = [link['node1'], link['node2']]
            for node_name in node_names:
                if node_name not in self.network.nodes:
                    self._debug('delete link: %s' % node_names)
                    deleted.append(link_id)
        for link_id in deleted:
            del self.network.links[link_id]

        self._fire_dpid_update(self.dpid)
        self._fire_port_map_update(self.port_map)

    def poll_netconf_agents(self, forced = False):
        "Poll netconf agents for VNF status updates"
        poll_period = 10
        if (time.time() - self.last_status_poll < poll_period) and not forced:
            return
        for sw in self.net.switches:
            if not sw.getAgent():
                continue
            i = self.vnf_manager.get_vnf_info_on_node(sw.name)
            # self._debug('VNF_INFO: %s' % i)
            visited = []
            for vnf_name, new_opts in i.iteritems():
                if vnf_name is None:
                    continue
                new_opts['parent'] = sw.name
                visited.append(vnf_name)
                orig = self.network.nodes.get(vnf_name, {})
                old_status = orig.get('status')
                if orig == new_opts:
                    # nothing's changed
                    continue
                orig.update(new_opts)
                self.network.nodes[vnf_name] = orig
                links = new_opts.get('link', [])
                if type(links) != list:
                    links = [links]
                self.found_vnf_links(vnf_name, links)
                if old_status != new_opts['status']:
                    self._fire_vnf_update(vnf_name, new_opts['status'])
            deleted = []
            for node_name, opts in self.network.nodes.iteritems():
                # self._debug('node_name: %s  opts: %s' % (node_name, opts))
                if opts.get('parent') != sw.name:
                    continue
                if node_name not in visited:
                    deleted.append(node_name)
            for vnf_name in deleted:
                del self.network.nodes[vnf_name]
                # self._debug('vnf_name: %s' % vnf_name)
                sw =  self.net.nameToNode[vnf_name]
                self.net.switches.remove(sw)
                del self.net.nameToNode[vnf_name]
                neighbours = self.port_map[vnf_name].keys()
                for n in neighbours:
                    del self.port_map[n][vnf_name]
                    # Assuming there can be only one link between n and vnf.
                    link = {'node1': n, 'node2': vnf_name,
                            'intf1': None, 'intf2': None, 'delete': True}
                    pox.core.core.raiseLater(self, LinkChange, **link)
                del self.port_map[vnf_name]
                self._fire_vnf_update(vnf_name, 'STOPPED')

        self.last_status_poll = time.time()

    def found_vnf_links(self, vnf_id, links):
        def get_intf_by_name(node, intf_name):
            for i in node.intfList():
                if str(i) == intf_name:
                    return i
            return None

        def get_or_create_intf(dev_name, obj, port):
            if port not in obj.intfs:
                # does not exist, let's create it
                return Intf(dev_name, node=obj, port=port)
            if str(obj.intfs[port]) != dev_name:
                # intf exists, but port is invalid
                return Intf(dev_name, node=obj, port=port)
            return obj.intfs[port]

        for i, link in enumerate(links):
            if int(link['sw_port']) == -1:
                # disconnected links (with port==-1) are omitted
                continue
            sw_name = link.get('sw_id', 'sw_id'+str(i))
            sw_dev = link.get('sw_dev', 'sw_dev'+str(i))
            sw_port = int(link['sw_port'])

            nf_name = vnf_id
            nf_dev  = link.get('vnf_dev', 'vnf_dev'+str(i))
            nf_port = int(link['vnf_port'])
            nf_mac = link['vnf_dev_mac']

            sw_obj = self.net.getNodeByName(sw_name)
            try:
                nf_obj = self.net.getNodeByName(nf_name)
            except KeyError:
                # this is a VNF not managed by mininet, yet we have to
                # add to the mininet 'database'.  TODO: Ideally, it
                # would be a RemoteHost, but for now it is a
                # RemoteSwitch.
                nf_obj = self.net.addRemoteSwitch(nf_name, dpid="-1")
            sw_i = get_or_create_intf(sw_dev, sw_obj, sw_port)
            if nf_dev in nf_obj.intfNames():
                nf_i = get_intf_by_name(nf_obj, nf_dev)
            else:
                nf_i = Intf(nf_dev, node=nf_obj, port=nf_port, mac=nf_mac)
                nf_i.mac = nf_mac # mn runs 'ifconfig', which resets mac to None

            self.found_link(sw_obj, nf_obj, sw_i, nf_i)

    def found_link(self, node_a, node_b, intf_a, intf_b):
        # link "A -> B" is the same as link "B -> A"
        link = [(node_a, intf_a), (node_b, intf_b)]
        link = sorted(link, key=lambda x: x[1])
        [(node1, intf1), (node2, intf2)] = link

        link_id = ''.join([intf1.name, intf2.name])
        orig_link = self.network.links.get(link_id, {})
        link = { 'node1': node1.name,
                 'node2': node2.name,
                 'intf1': intf1,
                 'intf2': intf2
                }
        try:
            self.port_map[node1.name][node2.name] = node1.ports[intf1]
        except KeyError:
            self.port_map[node1.name] = {node2.name: node1.ports[intf1]}

        try:
            self.port_map[node2.name][node1.name] = node2.ports[intf2]
        except KeyError:
            self.port_map[node2.name] = {node1.name: node2.ports[intf2]}

        if not cmp(orig_link, link) == 0:
            self.network.links[link_id] = link
            pox.core.core.raiseLater(self, LinkChange, **link)

    def found_node(self, node):
        orig = self.network.nodes.get(node.name, {})
        new_opts = copy.deepcopy(orig)
        new_opts['name'] = node.name
        new_opts['intf'] = {}
        for intf in node.intfList():
            new_opts['intf'][intf.name] = {'ip': node.IP(intf),
                                           'mac': node.MAC(intf),
                                           'port': node.ports[intf]}
        try:
            # taken form Node.connectionsTo
            for intf in node.intfList():
                link = intf.link
                if not intf.link:
                    continue
                node1, node2 = link.intf1.node, link.intf2.node
                if node1 == node or node2 == node:
                    self.found_link(node1, node2, link.intf1, link.intf2)
        except AttributeError:
            # network is not running
            return False

        if getattr(node, 'dpid', None):
            new_opts['dpid'] = int(node.dpid, base=16)
            self.dpid[node.name] = int(node.dpid, base=16)

        if not cmp(orig, new_opts) == 0:
            self.network.nodes[node.name] = new_opts
            pox.core.core.raiseLater(self, NodeChange,
                                     NodeChange.TYPE_DUMMY, **new_opts)
        return True

    def dpid_to_name(self, dpid):
        for name, name_dpid in self.dpid.iteritems():
            if dpid == name_dpid:
                return name
        return None

    def process_event_queue(self):
        processed = []
        for e in self.of_event_queue:
            name = self.dpid_to_name(e.dpid)
            if not name:
                continue
            e.name = name
            processed.append(e)
            self.fire(e.type, e)
        for e in processed:
            self.of_event_queue.remove(e)

    def change_network_state(self, new_state):
        if self.state == new_state:
            return
        self.state = new_state
        self._fire_network_state_change()

    #########
    ### Change Event generation and OpenFlow event handling
    #########
    def _fire_network_state_change(self):
        """Signalling the node/link params are changed"""
        event = Store()
        event.state = self.state
        self.fire('network_state_change', event)

    def _fire_dpid_update(self, dpids):
        event = Store()
        event.dpids = dpids
        self.fire('dpid_update', event)

    def _fire_port_map_update(self, port_map):
        event = Store()
        event.port_map = port_map
        self.fire('port_map_update', event)

    def _fire_switch_connection_up(self):
        pass

    def _fire_switch_connection_down(self):
        pass

    def _fire_vnf_update(self, vnf_name, status):
        m = {'FAILED': 'failed',
             'UP_AND_RUNNING': 'running',
             'INITIALIZING': 'starting',
             'STOPPED': 'stopped',
             }
        event = Store()
        event.name = vnf_name
        try:
            event.on_node = self.network.nodes[vnf_name]['parent']
        except KeyError:
            event.on_node = None
        event.status = m.get(status, 'failed')
        self.fire('vnf_update', event)

    def _handle_openflow_ConnectionUp(self, event):
        event.type = 'switch_connection_up'
        self.of_event_queue.append(event)

    def _handle_openflow_ConnectionDown(self, event):
        event.type = 'switch_connection_down'
        self.of_event_queue.append(event)

def launch():
    pox.core.core.register(NetworkManagerMininet())
