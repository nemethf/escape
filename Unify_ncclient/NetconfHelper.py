"""
 Copyright 2014 Levente Csikor <csikor@tmit.bme.hu>

 Licensed under the Apache License, Version 2.0 (the "License");
 you may not use this file except in compliance with the License.
 You may obtain a copy of the License at

 http://www.apache.org/licenses/LICENSE-2.0

 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS,
 WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 See the License for the specific language governing permissions and
 limitations under the License.
"""



import sys, os, warnings
import ncclient
from ncclient import manager

from ncclient import operations
from ncclient.operations import RPC
from ncclient.xml_ import *
from multiprocessing.managers import dispatch
import logging
from paramiko import hostkeys

from xml.etree import ElementTree
from lxml.etree import iselement
from xml.etree.ElementTree import tostringlist

from StringIO import StringIO
from __builtin__ import type

class RPCError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

class NetconfHelper:
    """
    This class is devoted to provide netconf specific callback functions and
    covering the background of how the netconf agent and the client work
    """
    
    

    def __init__(self, desired_logger_name = "UNIFY",**kwargs):
        """
        Constructor
        The important arguments should be set 
        (server, port, username, password, [timeout])
        For instance:
        netconf_helper = NetconfHelper( server = "localhost", 
                                        port = 831, 
                                        username = 'user', 
                                        password = 'secret_pass', 
                                        timeout = 30)
        
        DO NOT USE timeout=None -> it can cause errors, leave it empty, 
        this class may set it properly for you
        desired_logger_name: is for easier debugging...all the ncclient related
        logging will be starts with this unique string ([MY_NCCLIENT])
        """
        #setting up namespaces
        self.__NETCONF_NAMESPACE = u'urn:ietf:params:xml:ns:netconf:base:1.0'
        self.__RPC_NAMESPACE = u'http://csikor.tmit.bme.hu/netconf/unify/vnf_starter'
        
         #setting logging related stuffs
        self.__logger = logging.getLogger('[%s]' % desired_logger_name)
        self.__logger.setLevel(logging.DEBUG)
        self.__ch = logging.StreamHandler()
        self.__ch.setLevel(logging.DEBUG)
        
        formatter = logging.Formatter('%(asctime)s - '\
                                      '%(name)s - '\
                                      '%(levelname)s - '\
                                      '%(message)s')
        
        self.__ch.setFormatter(formatter)
        
        self.__logger.addHandler(self.__ch)
        #------------------------------
        
        
        print("---------------------------")
        self.__logger.info("NetconfHelper instantiated!")
#         print("---------------------------")
        self.__server = kwargs.get('server',None)
        self.__port = kwargs.get('port', None)
        self.__username = kwargs.get('username', None)
        self.__password = kwargs.get('password', None)
        self.__timeout = kwargs.get('timeout', 10)
        
        #variables for the last rpc reply
        self.__rpc_reply_formatted = dict()
        self.__rpc_reply_as_xml = ""

        #checking variables
        if(self.__server      == None or
           self.__port        == None or
           self.__username    == None or
           self.__password    == None):
            #connection variables were NOT set properly
            self.__logger.error("Connection information was not set properly!")
            self.__logger.error("Make sure you've set 'server', "\
                                                     "'port', "\
                                                     "'username', and "\
                                                     "'password' correctly")
    
        else:
            #connection variables were SET properly
            print("---------------------------")
            self.__logger.info("Connection parameters are set as follows:")
            self.__logger.info("Server: %s" % self.__server)
            self.__logger.info("Port: %s" % self.__port)
            self.__logger.info("Username: %s" % self.__username)
            self.__logger.info("Password: %s" % self.__password)
            self.__logger.info("Timeout for synchronous "\
                                "RPC request: %s" % self.__timeout)
            print("---------------------------")
            
            
   
    def connect(self):
        """
        This function will connect to the netconf server.
        The variable self.__connection is responsible for keeping 
        the connection up
        """
        self.__connection = ncclient.manager.connect(host=self.__server, 
                                                   port=self.__port, 
                                                   username=self.__username, 
                                                   password=self.__password, 
                                                   hostkey_verify=False,
                                                   timeout = self.__timeout)
        self.__logger.info("function (connect)Connected: %s" 
                         % self.__connection.connected)
   
    def disconnect(self):
        """
        This function will close the connection.
        """
        if(self.__connection.connected):
           self.__connection.close_session()
        self.__logger.info("function (disconnect)Connected: %s" 
                         % self.__connection.connected)
        
        
    
    def get_config_in_xml(self,source = 'running'):
        """
        This function will download the configuration of the netconf agent 
        into an xml file. 
        If source is None then the running config will be downloaded.
        Other configurations are netconf specific (RFC 6241) - 
        running,candidate,startup
        """
        s = source
        config = self.__connection.get_config(source=s).data_xml
        with open(("%s_%s.xml" % (self.__server,s)), 'w') as f:
            f.write(config)
            
    def get(self, expr = "/proc/meminfo"):
        """
        This process works as yangcli's GET function. A lot of information can 
        be got from the running netconf agent. If an xpath-based expression is 
        also set, the results can be filtered.
        The results are not printed out in a file, it's only printed to stdout
        """
        reply = self.__connection.get(filter=('xpath',expr)).data_xml
        print(type(reply))
    
    
    def __remove_namespace(self, ele, namespace = None):
        """ 
        Own function to remove the ncclient's namespace prefix, 
        because it causes "definition not found error" if OWN modules 
        and RPCs are being used
        """ 
        if(namespace != None):
            ns = u'{%s}' % namespace
            ns1 = len(ns)
            for elem in ele.getiterator():
                if elem.tag.startswith(ns):
    #                 print elem.attrib
                    elem.tag = elem.tag[ns1:]
    
        return ele
        
   
    def setRpcNamespace(self,namespace):
        """
        Function to set/change the RPC's namespace
        namespace: string
        """
        self.__RPC_NAMESPACE = u'%s' % namespace
        
    def getRpcNamespace(self):
        """
        Function to get actual RPC namespace
        """
        return self.__RPC_NAMESPACE
        
    def rpc(self, 
            rpc_name, 
            autoparse = True,
            options = {},
            switches = [],
            **input_params):
        """
        This function is devoted to call an RPC, and parses the rpc-reply 
        message (if needed) and returns every important parts of it in as
        dictionary
        rpc_name (text): your RPC's name
        rpc_namespace (text): your MODULE's namespace
        autoparse (boolean): indication to automatically parse the rpc-reply
        message, or just return it as an xml-string to leave parsing to the
        developer 
        options (dict): any further additional rpc-input can be passed towards,
        if netconf agent has this input list, called 'options'
        switches (list): it is used for connectVNF rpc in order to set the 
        switches where the vnf should be connected
        **input_params: dictionary of the input params for your RPC
        """
                       
        #create the desired xml element
        xsd_fetch = new_ele(rpc_name)
        #set the namespace of your rpc
        xsd_fetch.set('xmlns', self.__RPC_NAMESPACE)
        
        
        #set input params if they were set
        for k,v in input_params.iteritems():
            if type(v)==list:
                for element in v:
                    sub_ele(xsd_fetch, k).text = str(element)
            else:
                sub_ele(xsd_fetch, k).text = str(v)
    
        #setting options if they were sent
        for k,v in options.iteritems():
            option_list = sub_ele(xsd_fetch, "options")
            sub_ele(option_list, "name").text = k
            sub_ele(option_list, "value").text = v 

        #processing switches list
        for i,switch in enumerate(switches):
            sub_ele(xsd_fetch, "switch_id").text = switch
            

        
        #we need to remove the confusing netconf namespaces 
        #with our own function
        rpc = self.__remove_namespace(xsd_fetch, self.__NETCONF_NAMESPACE)
        
        #show how the created rpc message looks like
        print "GENERATED RPC MESSAGE:\n"
        print(etree.tostring(rpc,pretty_print=True))
        
        #SENDING THE CREATED RPC XML to the server
        #rpc_reply = without .xml the reply has GetReply type
        #rpc_reply = with .xml we convert it to xml-string
        try:
            rpc_reply = self.__connection.dispatch(rpc).xml
        except (ncclient.operations.rpc.RPCError) as e:
            self.__logger.info("ncclient: RPCError: %s" % e)
            raise RPCError(e)
            return None
        except (ncclient.transport.TransportError) as e:
            self.__logger.info("ncclient: TransportError % s" % e)
            #self.connect()
            raise RPCError(e)
            return None
        except (ncclient.operations.rpc.OperationError) as e:
            self.__logger.info("ncclient: OperationError: %s" % e)
            # self.__logger.info("function (connect)Connected: %s" 
            #                    % self.__connection.connected)
            # self.connect()
            raise RPCError(e)
            return None

        
        #we set our global variable's value to this xml-string
        #therefore, last RPC will always be accessible
        self.__rpc_reply_as_xml = rpc_reply
        print self.__rpc_reply_as_xml
        
        #we have now the rpc-reply
        #if autoparse is False, then we can greatfully break the process of 
        #this function and return the rpc-reply
        if not autoparse:
            return self.__rpc_reply_as_xml
        
        #in order to handle properly the rpc-reply as an xml element we need to
        #create a new xml_element from it, since another BRAINFUCK arise around
        #namespaces 
        #CREATE A PARSER THAT GIVES A SHIT FOR NAMESPACE
        parser = etree.XMLParser(ns_clean=True)
        #PARSE THE NEW RPC-REPLY XML
        dom = etree.parse(StringIO(rpc_reply),parser)
                
        #dom.getroot() = <rpc_reply .... > ... </rpc_reply>
        mainContents = dom.getroot()
       
        #alright, lets get all the important data with the following recursion
        parsed = self.__getChildren(mainContents, self.__RPC_NAMESPACE)
        self.__rpc_reply_formatted = parsed

#         print self.__rpc_reply_formatted        
        return self.__rpc_reply_formatted
    
    
    def __getChildren(self, ele, namespace = None):
        """
        This is an inner function, which is devoted to automatically analyze
        the rpc-reply message and iterate through all the xml elements until
        the last child is found, and then create a dictionary 
        Return a dict with the parsed data.
        """
    
        parsed = {} # parsed xml subtree as a dict
        if (namespace != None):
            ns = "{%s}" % namespace
            
        
        for i in ele.iterchildren():
            
            if(i.getchildren()):
                #still has children! Go one level deeper with recursion
                val = self.__getChildren(i, namespace)
                key = i.tag.replace(ns,"")   
            else:
                #if <ok/> is the child, then it has only <rpc-reply> as ancestor
                #so we do not need to iterate through <ok/> element's ancestors
                if(i.tag == "{%s}ok" % self.__NETCONF_NAMESPACE):
                    key = "rpc-reply"
                    val = "ok"
                else:     
                    key = i.tag.replace(ns,"")
                    val = ele.findtext("%s%s" % (ns,i.tag.replace(ns,"")))

            if key in parsed:
                if type(parsed[key]) == list:
                    parsed[key].append(val)
                else:
                    # had only one element, convert to list
                    parsed[key] = [parsed[key], val]
            else:
                parsed[key] = val

        return parsed                

            
           
            
        
        
        
