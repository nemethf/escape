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

'''
Created on May 29, 2014

@author: csoma
'''
import unittest
from Orchestrator import Mapping, DefaultSorter, NetworkGraphManager
from Orchestrator import Store


class TestOrchestrator(unittest.TestCase):


    def setUp(self):
        self.def_views = ['NF_CHAIN', 'PHY']
        self.nm = NetworkGraphManager(views = self.def_views,
                                 chain_view = self.def_views[0],
                                 res_view = self.def_views[1])

#     def test_initialization(self):

    def test_add_node(self):
        node_id = 0
        view = self.def_views[0]
        self.assertEqual(0, len(self.nm.graphs[view].node))
        self.nm.add_node(node_id, view)

        #node numero 1 created
        self.assertEqual(1, len(self.nm.graphs[view].node))
        self.assertIsNotNone(self.nm.graphs[view][node_id])

        #can not add node1 again
        self.assertRaises(RuntimeError, self.nm.add_node, node_id, view)

        #with empty parameter list
        self.assertDictEqual(dict(), self.nm.graphs[view][node_id])
        self.assertEqual(0, len(self.nm.graphs[view].node[node_id]))

        node_id += 1
        #add new node with some parameter
        self.nm.add_node(node_id, view, weight = 1, size = 2)
        #node numero 2 created
        self.assertEqual(2, len(self.nm.graphs[view].node))
        self.assertIsNotNone(self.nm.graphs[view][node_id])
        #parameters added
        self.assertEqual(2, len(self.nm.graphs[view].node[node_id]))
        self.assertDictEqual({'weight': 1, 'size': 2},
                             self.nm.graphs[view].node[node_id])

        #add new node to another view
        new_view = self.def_views[1]
        #add new node with some parameter
        self.nm.add_node(node_id, new_view, weight = 1, size = 2)
        #node numero 1 created
        self.assertEqual(1, len(self.nm.graphs[new_view].node))
        self.assertIsNotNone(self.nm.graphs[new_view].node[node_id])
        #parameters added
        self.assertEqual(2, len(self.nm.graphs[new_view].node[node_id]))
        self.assertDictEqual({'weight': 1, 'size': 2},
                             self.nm.graphs[new_view].node[node_id])

        #previous view remained untouched
        self.assertEqual(2, len(self.nm.graphs[view].node))

    def test_id_autoincrement(self):
        self.nm.auto_id = True

        node_id = 'A'
        view = self.def_views[0]
        self.assertEqual(0, len(self.nm.graphs[view].node))
        real_node_id = self.nm.add_node(node_id, view)

        #auto_id_node overrides the value of the id in the parameter list
        #node numero 1 created
        self.assertEqual(1, len(self.nm.graphs[view].node))
        self.assertNotIn(node_id, self.nm.graphs[view].node)
        self.assertIsNotNone(self.nm.graphs[view].node[real_node_id])

        #node numero 2 created
        real_node_id2 = self.nm.add_node(node_id, view)
        self.assertEqual(2, len(self.nm.graphs[view].node))
        self.assertNotIn(node_id, self.nm.graphs[view].node)
        self.assertIsNotNone(self.nm.graphs[view].node[real_node_id2])

        self.nm.auto_id = False
        self.assertRaises(RuntimeError, self.nm.add_node, None, view)

    def test_remove_node(self):
        node_id = 0
        view = self.def_views[0]

        #empty graph
        self.assertEqual(0, len(self.nm.graphs[view].node))

        self.nm.add_node(node_id, view)
        #node inserted
        self.assertIn(node_id, self.nm.graphs[view].node)

        self.nm.add_node(node_id+1, view)
        #node inserted
        self.assertIn(node_id, self.nm.graphs[view].node)

        self.nm.remove_node(node_id, view)
        #node removed
        self.assertNotIn(node_id, self.nm.graphs[view].node)

        self.nm.remove_node(node_id+1, view)
        #node removed
        self.assertNotIn(node_id+1, self.nm.graphs[view].node)

        #empty graph
        self.assertFalse(self.nm.graphs[view].graph)

    def test_modify_node(self):
        node_id = 0
        view = self.def_views[0]

        #node not in the graph
        self.assertNotIn(node_id, self.nm.graphs[view].node)

        #can not modify node which one does not exists
        self.assertRaises(RuntimeError, self.nm.modify_node, node_id, view)

        self.nm.add_node(node_id, view, weight = 2, size = 3)
        #node inserted
        self.assertIn(node_id, self.nm.graphs[view].node)
        #check parameters
        self.assertEqual(2, self.nm.graphs[view].node[node_id]['weight'])
        self.assertEqual(3, self.nm.graphs[view].node[node_id]['size'])

        #modify size
        self.nm.modify_node(node_id, view, size = 6)
        #check parameters
        self.assertEqual(2, self.nm.graphs[view].node[node_id]['weight'])
        self.assertEqual(6, self.nm.graphs[view].node[node_id]['size'])

    def test_add_remove_link(self):
        u = 1
        v = 2
        view = self.def_views[0]

        #add source and target
        self.nm.add_node(u, view)
        self.nm.add_node(v, view)

        #there is no link between u and v yet
        self.assertEqual(0, self.nm.graphs[view].number_of_edges(u,v))

        self.nm.add_link(u, v, view)

        #there is one link between u and v
        self.assertEqual(1, self.nm.graphs[view].number_of_edges(u,v))

        #test if there is only one link possible between nodes
        self.nm.add_link(u, v, view)

        #there is one link between u and v
        self.assertEqual(1, self.nm.graphs[view].number_of_edges(u,v))

        #remove link between u and v
        self.nm.remove_link(u, v, view)

        #there is no link between u and v
        self.assertEqual(0, self.nm.graphs[view].number_of_edges(u,v))

    def test_modify_link_parameters(self):
        u = 1
        v = 2
        view = self.def_views[0]

        #add source and target
        self.nm.add_node(u, view)
        self.nm.add_node(v, view)

        #there is no link between u and v yet
        self.assertEqual(0, self.nm.graphs[view].number_of_edges(u,v))

        self.nm.add_link(u, v, view, weight = 2, length = 4)

        self.assertIn('weight', self.nm.graphs[view].edge[u][v])
        self.assertIn('length', self.nm.graphs[view].edge[u][v])

        self.assertEqual(2, self.nm.graphs[view].edge[u][v]['weight'])
        self.assertEqual(4, self.nm.graphs[view].edge[u][v]['length'])

        #modify link's length
        self.nm.add_link(u, v, view, length = 8)

        self.assertEqual(2, self.nm.graphs[view].edge[u][v]['weight'])
        self.assertEqual(8, self.nm.graphs[view].edge[u][v]['length'])

    def test_add_chains(self):
        self.nm.auto_id = True
        view = self.def_views[0]

        #empty graph
        self.assertEqual(0, len(self.nm.graphs[view].node))
        #add an empty chain and test return parameters
        (chain_id, start_id, end_id) = self.nm.add_new_chain()
        self.assertIn(chain_id, self.nm.chains)
        self.assertIn(start_id, self.nm.graphs[view].node)
        self.assertIn(end_id, self.nm.graphs[view].node)
        self.assertEqual(start_id, self.nm.chains[chain_id]['source'])
        self.assertEqual(end_id, self.nm.chains[chain_id]['target'])

        #Test if auto_id overrides parameters
        (chain_id, start_id, end_id) = self.nm.add_new_chain('start', 'end')
        self.assertNotEqual(start_id, 'start')
        self.assertNotEqual(end_id, 'end')
        self.assertIn(chain_id, self.nm.chains)
        self.assertNotIn('start', self.nm.graphs[view].node)
        self.assertNotIn('end', self.nm.graphs[view].node)
        self.assertNotEqual('start', self.nm.chains[chain_id]['source'])
        self.assertNotEqual('end', self.nm.chains[chain_id]['target'])

        self.nm.auto_id = False
        #controlled chain add without auto id
        (chain_id, start_id, end_id) = self.nm.add_new_chain('start', 'end',
                                                               {'weight' : 3},
                                                               {'weight' : 5})
        self.assertIn(chain_id, self.nm.chains)
        self.assertIn('start', self.nm.graphs[view].node)
        self.assertIn('end', self.nm.graphs[view].node)
        self.assertIn('weight', self.nm.graphs[view].node['start'])
        self.assertEqual(3, self.nm.graphs[view].node['start']['weight'])
        self.assertEqual(5, self.nm.graphs[view].node['end']['weight'])
        self.assertEqual('start', self.nm.chains[chain_id]['source'])
        self.assertEqual('end', self.nm.chains[chain_id]['target'])

    def test_orchestrator_helpers(self):
        res_view = self.def_views[1]

        self.nm.auto_id = False
        phy_s = self.nm.add_node('phy_s', res_view,
                                 node_type = NetworkGraphManager.NODE_TYPE_SAP)
        phy_t = self.nm.add_node('phy_t', res_view,
                                 node_type = NetworkGraphManager.NODE_TYPE_SAP)

        res_g = self.nm.get_graph(res_view)

        stnodes = Mapping.get_stnodes(res_g)
        #there is no path between nodes
        self.assertEqual(stnodes, [])

        self.nm.add_link(phy_s, phy_t, res_view)
        stnodes = Mapping.get_stnodes(res_g)
        self.assertEqual(stnodes, [(phy_s, phy_t)])


        self.nm.auto_id = True
        (view, s_node, t_node, nodes) = self._add_one_vnf_chain()

        g = self.nm.get_graph(view)

        stnodes = Mapping.get_stnodes(g)

        #check if SAPs are in stnodes list
        self.assertIn((t_node, s_node), stnodes)

        #only one endpoint pair in this basic chain view
        self.assertEqual(1, len(stnodes))

        #add another node, and check if the two new SAP is added
        (chain_id, s_node2, t_node2) = self.nm.add_new_chain()
        self.nm.add_link(s_node2, t_node2, view)

        stnodes = Mapping.get_stnodes(g)

        #check if SAPs are in stnodes list
        self.assertIn((s_node2, t_node2), stnodes)

        #now the view has two chain and two st pair
        self.assertEqual(2, len(stnodes))

        #add a vnf node with dummy type to the view
        dummy_id = self.nm.add_node(None, view, node_type = 'dummy')
        self.nm.add_link(s_node2, dummy_id, view)

        #add a normal vnf node to the view
        true_vnf = self.nm.add_node(None, view,
                                    node_type = NetworkGraphManager.NODE_TYPE_VNF,
                                    req = {'cpu': 4, 'mem': 3})
        self.nm.add_link(dummy_id, true_vnf, view)
        self.nm.add_link(true_vnf, t_node2, view)

        #add an unreachable vnf node to the view
        unreach_vnf = self.nm.add_node(None, view,
                                       node_type = NetworkGraphManager.NODE_TYPE_VNF)

        #add a broken chain
        (chain_id3, s_node3, t_node3) = self.nm.add_new_chain()
        broken_vnf = self.nm.add_node(None, view,
                                      node_type = NetworkGraphManager.NODE_TYPE_VNF)
        self.nm.add_link(s_node3, broken_vnf, view)


        stnodes = Mapping.get_stnodes(g)
        vnf_list = Mapping.get_accessible_vnf_list(stnodes, g)

        #dummy not in the vnf list, because its type
        self.assertNotIn(dummy_id, vnf_list)
        #broken not in the vnf list, because its chain is not valid
        self.assertNotIn(broken_vnf, vnf_list)
        #unreach not in the vnf list, because it is unreachable
        self.assertNotIn(unreach_vnf, vnf_list)

        self.assertIn(true_vnf, vnf_list)

        #Test, if we add a vnf to a phy node, resources are globally updated
        phy_view = self.def_views[1]
        phy_g = self.nm.get_graph(phy_view)
        phy_node1 = self.nm.add_node(None, phy_view, res = {'cpu': 6, 'mem': 3})
        Mapping.add_vnf_to_host(true_vnf, phy_node1, g, phy_g)

        phy_node = self.nm.graphs[phy_view].node[phy_node1]
        self.assertEqual(2, phy_node['res']['cpu'])
        self.assertEqual(0, phy_node['res']['mem'])

    def test_default_sorter(self):
        view = self.def_views[0]
        self.nm.auto_id = True
        node1 = self.nm.add_node(None, view, req = {'cpu': 4, 'mem': 3})
        node2 = self.nm.add_node(None, view, req = {'cpu': 5, 'mem': 3})
        node3 = self.nm.add_node(None, view, req = {'cpu': 4, 'mem': 1})

        vnf_list = {node1: node1, node2: node2, node3: node3}

        sorter = DefaultSorter()
        sorted = sorter.order_vnf_list(vnf_list, self.nm.graphs[view])

        #DefaultSorter sorts vnf list in ascending order first comparing
        #cpu needs than memory requirements

        self.assertEqual(sorted[0], node3)
        self.assertEqual(sorted[1], node1)
        self.assertEqual(sorted[2], node2)

        #Test if node chooser returns with res_node with highest available
        #resources
        phy_view = self.def_views[1]
        phy_node1 = self.nm.add_node(None, phy_view,
                                     res = {'cpu': 1, 'mem': 3},
                                     node_type = NetworkGraphManager.NODE_TYPE_HOST)
        phy_node2 = self.nm.add_node(None, phy_view,
                                     res = {'cpu': 14, 'mem': 3},
                                     node_type = NetworkGraphManager.NODE_TYPE_HOST)
        phy_node3 = self.nm.add_node(None, phy_view,
                                     res = {'cpu': 4, 'mem': 1},
                                     node_type = NetworkGraphManager.NODE_TYPE_HOST)

        vnf = Store()
        vnf.node = {'req': {'cpu': 1, 'mem': 1}}
        host = sorter.get_node_for_vnf(vnf, self.nm.graphs[view],
                                       self.nm.graphs[phy_view])

        self.assertEqual(host, phy_node2)

        #If there is not enough resource in physical nodes
        #get_node_for_vnf returns None
        vnf.node = {'req': {'cpu': 100, 'mem': 100}}
        host = sorter.get_node_for_vnf(vnf, self.nm.graphs[view],
                                       self.nm.graphs[phy_view])

        self.assertEqual(None, host)

        #if there is overlapping, highest cpu value wins
        #e.g: node1: cpu: 10, mem: 4; node2: cpu:5, mem: 7, than algorithm
        #returns with node1
        self.nm.modify_node(phy_node1, phy_view, res = {'cpu': 9, 'mem': 13})
        vnf.node = {'req': {'cpu': 1, 'mem': 1}}
        host = sorter.get_node_for_vnf(vnf, self.nm.graphs[view],
                                       self.nm.graphs[phy_view])

        self.assertEqual(phy_node2, host)


    def test_orchestrating(self):
        res_view = 'RES'
        chain_view = 'CHAIN'
        self.nm = NetworkGraphManager(auto_id = False,
                                 views = [chain_view, res_view],
                                 chain_view = chain_view,
                                 res_view = res_view)

        #build a basic chain network
        (chain_id, start_id, end_id) = self.nm.add_new_chain('start1', 'end1')
        vnf_node_id = self.nm.add_node('vnf1', chain_view,
                                       node_type = NetworkGraphManager.NODE_TYPE_VNF,
                                       req = {'cpu': 4, 'mem': 4})
        vnf_node_id2 = self.nm.add_node('vnf2', chain_view,
                                        node_type = NetworkGraphManager.NODE_TYPE_VNF,
                                        req = {'cpu': 7, 'mem': 4})

        self.nm.add_link(start_id, vnf_node_id, chain_view)
        self.nm.add_link(vnf_node_id, vnf_node_id2, chain_view)
        self.nm.add_link(vnf_node_id2, end_id, chain_view)

        #build a basic phy network
        phy1_id = self.nm.add_node('phy1', res_view,
                           node_type = NetworkGraphManager.NODE_TYPE_HOST,
                           res = {'cpu': 2, 'mem': 3})

        phy2_id = self.nm.add_node('phy2', res_view,
                           node_type = NetworkGraphManager.NODE_TYPE_HOST,
                           res = {'cpu': 4, 'mem': 3})

        self.nm.add_link(phy1_id, phy2_id, res_view)

        chain_g = self.nm.get_graph(chain_view)
        res_g = self.nm.get_graph(res_view)
        #start end end nodes are not presented in the physical view
        self.assertRaises(RuntimeError, Mapping.map,
                          chain_g, res_g, DefaultSorter)

        self.nm.add_node('start1', res_view,
                         node_type = NetworkGraphManager.NODE_TYPE_SAP)
        self.nm.add_node('end1', res_view,
                         node_type = NetworkGraphManager.NODE_TYPE_SAP)
        #start end end nodes are not connected in the physical view
        self.assertRaises(RuntimeError, Mapping.map,
                          chain_g, res_g, DefaultSorter)

        self.nm.add_link('start1', 'end1', res_view)
        pair_list = Mapping.map(chain_g, res_g, DefaultSorter)

        #Not enough resource available in res view, so we get an empty pair list
        self.assertFalse(pair_list)

        self.nm.modify_node(phy2_id, res_view, res = {'cpu': 11, 'mem': 8})
        pair_list = Mapping.map(chain_g, res_g, DefaultSorter)
        self.assertIn((vnf_node_id, phy2_id), pair_list)
        self.assertIn((vnf_node_id2, phy2_id), pair_list)

        self.nm.modify_node(phy2_id, res_view, res = {'cpu': 8, 'mem': 4})
        self.nm.modify_node(phy1_id, res_view, res = {'cpu': 7, 'mem': 4})
        pair_list = Mapping.map(chain_g, res_g, DefaultSorter)
        self.assertIn((vnf_node_id, phy2_id), pair_list)
        self.assertIn((vnf_node_id2, phy1_id), pair_list)

    def _add_one_vnf_chain(self):
        view = self.def_views[0]
        self.nm.auto_id = True

        (chain_id, start_id, end_id) = self.nm.add_new_chain()
        vnf_node_id = self.nm.add_node(None, view,
                                       node_type = NetworkGraphManager.NODE_TYPE_VNF)
        self.nm.add_link(start_id, vnf_node_id, view)
        self.nm.add_link(vnf_node_id, end_id, view)

        return (view, start_id, end_id, [vnf_node_id])

if __name__ == "__main__":
    unittest.main()