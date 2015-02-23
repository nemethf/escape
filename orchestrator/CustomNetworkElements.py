"""
Based on MiniEdit: a simple network editor for Mininet

Bob Lantz, April 2010
Gregory Gee, July 2013

Controller icon from http://semlabs.co.uk/
OpenFlow icon from https://www.opennetworking.org/
"""

from mininet.node import RemoteController, UserSwitch, Node, OVSSwitch
import Utils


class InbandController(RemoteController):
    def checkListening(self):
        """Overridden to do nothing."""
        return


class CustomUserSwitch(UserSwitch):
    def __init__(self, name, dpopts='--no-slicing', **kwargs):
        UserSwitch.__init__(self, name, dpopts, **kwargs)
        self.switchIP = None

    def getSwitchIP(self):
        return self.switchIP

    def setSwitchIP(self, ip):
        self.switchIP = ip

    def start(self, controllers):
        # Call superclass constructor
        UserSwitch.start(self, controllers)
        # Set Switch IP address
        if self.switchIP is not None:
            if not self.inNamespace:
                self.cmd('ifconfig', self, self.switchIP)
            else:
                self.cmd('ifconfig lo', self.switchIP)


class LegacyRouter(Node):
    def __init__(self, name, inNamespace=True, **params):
        Node.__init__(self, name, inNamespace, **params)

    def config(self, **_params):
        if self.intfs:
            self.setParam(_params, 'setIP', ip='0.0.0.0')
        r = Node.config(self, **_params)
        self.cmd('sysctl -w net.ipv4.ip_forward=1')
        return r


class LegacySwitch(OVSSwitch):
    def __init__(self, name, **params):
        OVSSwitch.__init__(self, name, failMode='standalone', **params)
        self.switchIP = None


class customOvs(OVSSwitch, Utils.LoggerHelper):
    def __init__(self, name, failMode='secure', datapath='kernel', **params):
        OVSSwitch.__init__(self, name, failMode=failMode, datapath=datapath, **params)
        self.openFlowVersions = []
        self.switchIP = None

    def getSwitchIP(self):
        return self.switchIP

    def setSwitchIP(self, ip):
        self.switchIP = ip

    def getOpenFlowVersion(self):
        return self.openFlowVersions

    def setOpenFlowVersion(self, versions):
        if versions['ovsOf10'] == '1':
            self.openFlowVersions.append('OpenFlow10')
        if versions['ovsOf11'] == '1':
            self.openFlowVersions.append('OpenFlow11')
        if versions['ovsOf12'] == '1':
            self.openFlowVersions.append('OpenFlow12')
        if versions['ovsOf13'] == '1':
            self.openFlowVersions.append('OpenFlow13')

    def configureOpenFlowVersion(self):
        if not ('OpenFlow11' in self.openFlowVersions or
                'OpenFlow12' in self.openFlowVersions or
                'OpenFlow13' in self.openFlowVersions):
            return

        protoList = ",".join(self.openFlowVersions)
        self._info('Configuring OpenFlow to %s' % protoList)
        self.cmd('ovs-vsctl -- set bridge', self, 'protocols=' + protoList)

    def start(self, controllers):
        # Call superclass constructor
        OVSSwitch.start(self, controllers)
        # Set OpenFlow VersionsHost
        self.configureOpenFlowVersion()
        # Set Switch IP address
        if self.switchIP is not None:
            self.cmd('ifconfig', self, self.switchIP)
