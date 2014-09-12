#                                                 -*- mode: python -*-
#
#  This file should contain one list of dictionaries, each dictionary
#  defining one VNF.  The format used here is far from ideal.
#
#  * The names in keywords and in the command templates different.
#    For example, 'mac' and \$MAC in the headerDecompressor.
#
#  * Metadata and configuration parameters are indistinguishable.
#    This prevents automatically creating a GUI in which
#    conf. parameters could be set.  (E.g., 'description' and
#    'cpu-util' in case of lookbusy)
#
#   The name of the class responsible for assembling the final command
#   line is derived from the 'type' value.  For type 'Foo' there
#   should be a class named 'VnfFoo' in vnfcatalog.py
#
[ {'name': 'dummy',
   'description': 'Set up an empty module (for testing)',
   'type': 'Click',              # random comment
   'builder_class': 'VNFClickBuilder'
  },
  {'name': 'simpleForwarder',
   'description': """NFV defaults
        '(receive on the data interface and loop back the packet)""",
   'type': 'Click',
   'command': """FromDevice(\$VNFNAME-eth1)->Queue(1000)
                                           ->ToDevice(\$VNFNAME-eth1)""",
   'icon': 'forward.png', # searched in directory 'res'
   'builder_class': 'VNFClickBuilder'
  },
  {'name': 'simpleObservationPoint',
   'description': 'A simple observation point in click',
   'type': 'Click',
   'output': True,
   'builder_class': 'VNFClickBuilder',
   'command': """

        define(\$DEV \$VNFNAME-eth1, \$DADDR 10.0.0.1, \$GW \$DEV:gw, \$METHOD PCAP,\$LIMIT -1, \$INTERVAL 1)

        FromDevice(\$DEV, METHOD \$METHOD)
        -> tee::Tee(3)

        output :: Queue -> ToDevice(\$DEV);

        // To put into a service chain edit this
        tee[0] -> cnt :: Counter -> output;

        tee[1]
        -> c :: Classifier(12/0800, 12/0806 20/0002)
        -> CheckIPHeader(14)
        -> ip :: IPClassifier(icmp echo-reply)
        -> ping :: ICMPPingSource(\$DEV, \$DADDR, INTERVAL \$INTERVAL,LIMIT \$LIMIT, ACTIVE true)
        -> SetIPAddress(\$GW)
        -> arpq :: ARPQuerier(\$DEV)
        -> output;

        arpq[1]-> output;
        c[1]-> [1] arpq;

        cl :: Classifier(12/0800,-)
        af :: AggregateIPFlows(TRACEINFO alma.xml)

        tee[2] -> cl
        -> Strip(14)
        -> CheckIPHeader
//        -> IPPrint(OK)
        -> af
        -> AggregateCounter
        -> IPRateMonitor(PACKETS, 0.5, 256, 600)
        -> Discard

        cl[1]->Discard;

"""
  },
  {'name': 'headerCompressor',
   'description': 'Compress IPv4/TCP headers as defined in RFC2507',
   'type': 'Click',
   'output': True,
   'icon': 'compress2_small.png',
   'builder_class': 'VNFClickBuilder',
   'command': """

        output :: Queue -> Print(comp) -> ToDevice(\$VNFDEV0);

        FromDevice(\$VNFDEV0)
        -> c :: Classifier(12/0800, -)
        -> cnt :: Counter
        -> Strip(14)
        -> CheckIPHeader
	-> compr :: RFC2507Comp
        -> EtherEncap(0x22F1, 1:1:1:1:1:1, FF:FF:FF:FF:FF:FF)
        -> output
        c[1] -> output
"""
  },
  {'name': 'headerDecompressor',
   'description': 'Decompress IPv4/TCP headers as defined in RFC2507',
   'type': 'Click',
   'output': True,
   'icon': 'decompress_small.png',
   'builder_class': 'VNFClickBuilder',
   'command': """
        output :: Queue -> ToDevice(\$VNFDEV0);

        FromDevice(\$VNFDEV0)
        -> c :: Classifier(12/22F1, -)
        -> cnt :: Counter
        -> Strip(14)
	-> decompr :: RFC2507Decomp
        -> EtherEncap(0x0800, 2:2:2:2:2:2, 6:5:4:3:2:1)
        -> output
        c[1] -> output
"""
  },
  {'name': 'lookbusy',
   'type': 'LookBusy',
   'builder_class': 'VNFClickBuilder',
   'description':
     """Generate load using 'lookbusy' for testing VNF load balancers
     You can specify the following long options of lookbusy:
     verbose, quiet, cpu-util, ncpus, cpu-mode, cpu-curve-period,
     cpu-curve-peak, utc, mem-util, mem-sleep, disk-util, disk-sleep,
     disk-block-size, disk-path
     """,
  },
  {'name': 'fakeLoad',
   'type': 'FakeLoad',
   'builder_class': 'VNFClickBuilder',
   'description': 'Generate load using LookBusy for testing VNF load balancers',
   'cpu': 8,
   'mem': '5MB',
  },
  {'name': 'netconf',
   'type': 'NetConf',
   'builder_class': 'VNFClickBuilder', #maybe use different builder class
   'description': 'Launch NetConf-based managers',
  },
]
