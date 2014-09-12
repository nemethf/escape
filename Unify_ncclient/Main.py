#!/usr/bin/python

from NetconfHelper import NetconfHelper, RPCError

def main():
#     instanciate class
    netconf_helper = NetconfHelper(server = "localhost", 
                                   port = 830, 
                                   username = 'mininet', 
                                   password = 'mininet',
                                   timeout=30)
    
# connect to server
    netconf_helper.connect()
#     print type(netconf_helper.getRpcNamespace())
    
#     netconf_helper.setRpcNamespace("http://csikor.tmit.bme.hu/netconf/unify/test")
#     print type(netconf_helper.getRpcNamespace())

#     load = netconf_helper.rpc("make-toast",toasterDoneness=1,toasterToastType="toast:wheat-bread")
    initVNF = netconf_helper.rpc("initiateVNF", vnf_type="TEST", options = {"ip": "127.0.0.1"})
    initVNF2 = netconf_helper.rpc("initiateVNF", vnf_type="TEST", options = {"ip": "127.0.0.1", "bacon" : "yes"})
    print repr(initVNF)
    print repr(initVNF2)
    vnf_id_1 = initVNF['access_info']['vnf_id']
    vnf_id_2 = initVNF2['access_info']['vnf_id']
    print "VNF id 1: %s" % vnf_id_1
    print "VNF id 2: %s" % vnf_id_2
#     for k in initVNF:
#         print("%s - %s" % (k,initVNF[k]))

    connectVNF = netconf_helper.rpc("connectVNF", vnf_id=vnf_id_1, vnf_port="0", switch_id="s3")
    connectVNF = netconf_helper.rpc("connectVNF", vnf_id=vnf_id_1, vnf_port="1", switch_id="s3")
    #    connectVNF = netconf_helper.rpc("connectVNF", vnf_id=vnf_id_2, vnf_port="0", switch_id="s4")
    print repr(connectVNF)
#     for k in connectVNF:
#         print("%s - %s" % (k,connectVNF[k]))
        
        
    #getting a vnf's vnf_dev assigned for a link
    getVNFInfo = netconf_helper.rpc("getVNFInfo")
    for vnf in getVNFInfo.get('initiated_vnfs', []):
        if vnf.get('vnf_id') != vnf_id_1:
            continue
        links = vnf['link']
        if type(links) != list:
            links = [links]
        for link in links:
            if link.get('vnf_port') == '0':
                print "ASDF: %s" % link.get('vnf_dev')

    

    #kill vnf
    try:
        status = netconf_helper.rpc("stopVNF", vnf_id=vnf_id_1)
        for k in status:
            print("%s - %s" % (k,status[k]))
    except RPCError as e:
        print "RPC ERROR OCCURRED: %s" % e
    
    
    # try:
    #     status = netconf_helper.rpc("stopVNF", vnf_id=vnf_id_2)
    #     for k in status:
    #         print("%s - %s" % (k,status[k]))
    # except RPCError as e:
    #     print "RPC ERROR OCCURRED: %s" % e
    
        
    netconf_helper.disconnect()
   

if __name__ == "__main__":main()
