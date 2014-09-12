/*
 * main.c
 *
 *  Created on: Jun 3, 2014
 *      Author: unify
 */

#include <stdio.h>

#include "vnfs.h"

int main (int argc, char **argv)
{


    vnf_initializer();

    gchar* vnf1 = createVNF();


	setControlIP(vnf1,"127.0.0.1");
	setControlPort(vnf1, "8001");

//	//create and connect veth devices
//	gchar* uny_pair = createVirtualEthernetPairs();
//	gchar* uny1 = subStringDeviceIdFromVirtualEthernetPair(uny_pair,0);
//	gchar* uny2 = subStringDeviceIdFromVirtualEthernetPair(uny_pair,1);

//	gchar* sw_port = connectVirtualEthernetDeviceToSwitch(uny2,"s1");
//	addSwitchConnectionToVNF(vnf1,"s1",TRUE);
//	addVirtualEthernetPairs("vnf_1",uny_pair,"s1",sw_port);
//
//	setVNFCommand(vnf1,
//				g_strdup_printf("click --port %s --ip %s -R --func=asd --dev=%s",
//								getControlPort(vnf1),
//								getControlIP(vnf1),
//								uny1));
	setVNFCommand(vnf1, "xterm");

//	setPid("vnf_1", 19588);

	connectVNF(vnf1,"0","s1");
	connectVNF(vnf1,"1", "s1");

	sleep(3);

    startVNF(vnf1);
//    printVNFs();

//	system("ls -l");
    sleep(1);
    stopVNF(vnf1);
//    sleep(3);
    printVNFs();

//    vnf1 = createVNF();
//    connectVNF(vnf1, "0", "s1");
//    printVNFs();
//
//    stopVNF(vnf1);
//    printVNFs();
//    stopVNF("vnf_1");
//    disconnectVNF("vnf_1",uny_pair);

//    printVNFs();
//    reconnectVNF("vnf_1",uny_pair);

//    startVNF(vnf1);
//    printVNFs();
//    sleep(5);
//    stopVNF(vnf1);
//    printVNFs();

/*
 * JUST FOR TESTING PURPOSES
 */
//    printf("PID of vnf_1: %d\n",getPid(vnfs,"vnf_1"));
//    printf("connected switches of vnf_1: \n");
//    print_list_data(getConnectedSwitches(vnfs,"vnf_1"));
//    removeSwitchConnectionFromVNF(vnfs,"vnf_1","SW_1");
//    printf("connected switches of vnf_1: \n");
//    print_list_data(getConnectedSwitches(vnfs,"vnf_1"));
//
//    addSwitchConnectionToVNF(vnfs,"vnf_1", "SW_3");
//    printf("connected switches of vnf_1: \n");
//	print_list_data(getConnectedSwitches(vnfs,"vnf_1"));

//  	addVirtualEthernetPairs(vnfs,"vnf_1","veth4-veth5","SW_5", "15");
//  	addVirtualEthernetPairs(vnfs,"vnf_1","veth6-veth7","SW_5", "15");
//
//  	removeVirtualEthernetPair(vnfs,"vnf_1","veth0-veth1");
//  	addVirtualEthernetPairs(vnfs,"vnf_1","veth0-veth1","SW_5", "1");
//    GHashTable *v_e_pairs = getVirtualEthernetPairs(vnfs,"vnf_1");
//    g_hash_table_foreach(v_e_pairs,
//        					(GHFunc)print_hashtable_values_as_list,
//        					 NULL);

//    removeVNF(vnfs,"vnf_1");
//    g_hash_table_foreach(vnfs, (GHFunc) print_data, NULL);
//    printf("Size of the vnfs' hashtable: %d", g_hash_table_size(vnfs));

//	g_print("Ports and device ids of switch s3\n");
//	g_hash_table_foreach(getAllSwitchPorts("s3"), (GHFunc) print_hashtable_values_as_gchar, NULL);
//
//	gchar* port = getSwitchPort("s3","uny_2");
//	if(port != NULL)
//	{
//	g_print("The port of device uny_2 attached to switch s3 is %s\n",port);
//	}
//	port = getSwitchPort("s3","uny_5");
//	if(port != NULL)
//	{
//	g_print("The port of device uny_2 attached to switch s3 is %s\n",port);
//	}

    return 0;
}


