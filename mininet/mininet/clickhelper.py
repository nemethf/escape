#!/usr/bin/python

# Copyright (c) 2014 Balazs Sonkoly
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
# along with this file. If not, see <http://www.gnu.org/licenses/>.

import os
import sys
import copy
import subprocess
import signal
import atexit
import time
from mininet.vnfcatalog import Catalog

class ClickHelper( object ):
    '''
    Helper class for starting Click-based VNFs
    VNF info is read from VNF catalog
    '''
    def __init__ (self):
        self.vnf_type = None
        self._parse_args()
        self.catalog = Catalog()
        self.click_proc = None
        atexit.register(self.kill_click_proc)

    def _parse_args(self):
        '''
        Loading command line args coming from netconfd to a dictionary
        Format: arg1=argval1 ar2=argval2 ...
        '''
        self.opts = dict(map(lambda x: x.split('='),sys.argv[1:]))
        self.updateDevs()

    def updateDevs(self):
        'Update devs list based on opts (ex: dev_x=uny_y)'
        devs = [(k, v) for k,v in self.opts.iteritems() if k.startswith('dev')]
        devs = dict(devs)
        devlist = []
        for k in sorted(devs.keys()):
            devlist.append(devs[k])
        self.opts.update({'devs': devlist})

    def setVNFType(self):
        'Set vnf_type based on opts'
        try:
            self.vnf_type = self.opts['type']
        except KeyError:
            self.vnf_type = None
        return self.vnf_type

    def getVNFType(self):
        return self.vnf_type

    def logVNFType(self):
        if self.vnf_type:
            #print self.vnf_type
            with open('/tmp/vnftype.log', 'w') as f:
                f.write(str(self.vnf_type))
                f.close()

    def initVNF(self):
        'Initialize VNF, make command'
        self.setVNFType()
        opts = copy.deepcopy(self.opts)
        startCmd = self.catalog.make_cmd(opts['type'],
                                         name = opts['vnf_id'],
                                         **self.opts)
        startCmd = startCmd.replace('&', ' ')
        self.startCmd = startCmd

    def getVNFCmd(self):
        return self.startCmd

    def logVNFCmd(self):
        if self.startCmd:
            print self.startCmd
            with open('/tmp/vnfcmd.log', 'w') as f:
                f.write(str(self.startCmd))
                f.close()
    
    def startVNF(self):
        '''Execute previously assembled VNF command
        output: -1: fork failed, high error code: invalid argument'''
        print self.startCmd
        #return os.system(self.startCmd)
        # return subprocess.call(['sh', '-c', self.startCmd])
        proc =  subprocess.Popen(['sh', '-c', self.startCmd])
        self.click_proc = proc
        #blocking parent
        output, error = proc.communicate()
        exitcode = proc.wait()
        return output, error, exitcode

    def kill_click_proc(self):
        if self.click_proc is None:
            pass
        else:
            print "Kill click process, PID: %s" % self.click_proc.pid
            self.click_proc.kill()

if __name__ == "__main__":
    ch = ClickHelper()
    ch.initVNF()
    ch.logVNFCmd()
    (output, error, exitcode) = ch.startVNF()
    print output
    print error
    print exitcode
