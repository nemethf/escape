"""
Extends Mininet CLI with sum-commands for interactive with VNFs.

Example session:

mininet> vnf info
mininet> ee status
mininet> ee help
mininet> ee
mininet:ee> status
mininet:ee> help
mininet:ee>
mininet>
"""

from os import kill
from time import sleep
from cmd import Cmd
import sys
import curses

from mininet.log import info, output, error
from mininet.util import quietRun
from mininet.vnfcatalog import Catalog

class SubCmd( Cmd ):
    "Base-class for sub-commands."

    def __init__( self ):
        Cmd.__init__( self )

    def complete_further(self, text, origline, begidx, endidx):
        """Return possible completions for 'text'.

        Suitable for hierarchical completion.
        """
        # based on Cmd.complete()
        line = origline.lstrip()
        stripped = len(origline) - len(line)
        begidx = begidx - stripped
        endidx = endidx - stripped
        if begidx>0:
            cmd, args, foo = self.parseline(line)
            if cmd == '':
                compfunc = self.completedefault
            else:
                try:
                    compfunc = getattr(self, 'complete_' + cmd)
                except AttributeError:
                    compfunc = self.completedefault
        else:
            compfunc = self.completenames
        return compfunc(text, line, begidx, endidx)

    def emptyline( self ):
        "Exit from the sub-interpreter."
        return True

    def do_exit( self, _line ):
        "Exit"
        return 'exited by user command'

    def do_quit( self, line ):
        "Exit"
        return self.do_exit( line )

    def do_EOF( self, line ):
        "Exit"
        output( '\n' )
        return self.do_exit( line )

class EE( SubCmd ):
    "Subcommands for interacting with EEs."

    prompt = 'mininet:ee> '

    def __init__( self, mininet, stdin=sys.stdin, script=None ):
        self.mn = mininet
        SubCmd.__init__( self )

    def do_status( self, _line ):
        "Print the status of Execution Environments (VNF containers)."
        for ee in self.mn.ees:
            if ee.vnfPid:
                try:
                    kill( ee.vnfPid, 0 )
                    output('%s is running %s at PID %s\n' %
                           (ee.name, ee.startCmd, ee.vnfPid))
                except:
                    ee.vnfPid = 0
                    output('%s is idle\n' % ee.name)
            else:
                output('%s is idle\n' % ee.name)

    def do_stop( self, _line ):
        "Stop VNFs running inside EEs."
        self.mn.stopVNFs()

    def do_start( self, _line ):
        "Start VNFs associated with EEs."
        self.mn.startVNFs()

    def do_restart( self, _line ):
        "Restart VNFs associated with EEs."
        self.mn.restartVNFs()

    def do_top( self, _line ):
        "Show resource usage for EEs."
        cmd = 'grep cpu /proc/stat'
        mcmd = 'grep MemTotal /proc/meminfo'
        mem_total = int( quietRun( mcmd ).split()[-2] )
        last_cpu_usage = {}
        last_cpu_total = {}
        for ee in self.mn.ees:
            last_cpu_usage[ee] = 1
            last_cpu_total[ee] = 1

        screen = curses.initscr()
        curses.noecho()
        screen.clear()
        #curses.curs_set(0)
        
        h1 = "\t[         CPU         ]\t[             MEM              ] "
        h2 = " NAME\t[  SHARE   ABS    REL ]\t[ TOTAL kB USED kB   ABS   REL ]"
        while True:
            vpos=2
            hpos=0
            screen.addstr(0, 0, h1)
            screen.addstr(1, 0, h2)
            for ee in self.mn.ees:
                procresult = quietRun( cmd ).split()
                cpu_total = sum( map(int, procresult[1:10]) )
                cpu_usage = ee.cGetCpuUsage()
                diff = float(cpu_usage-last_cpu_usage[ee])
                total_diff = float(cpu_total-last_cpu_total[ee])
                last = last_cpu_total[ee]
                cpu_usage_abs = 100.0 * diff / total_diff
                cpu_usage_rel = cpu_usage_abs / ee.frac
                mem_usage = ee.cGetMemUsage()
                mem_usage_abs = 100.0 * mem_usage / mem_total
                mem_usage_rel = mem_usage_abs / ee.frac
                s = " %s" % ee.name
                s += '\t%7.1f' % ee.frac
                s += ' %6.1f' % cpu_usage_abs
                s += ' %6.1f' % cpu_usage_rel
                s += '\t%10d' % mem_total
                s += ' %7d' % mem_usage
                s += ' %5.1f' % mem_usage_abs
                s += ' %5.1f' % mem_usage_rel
                screen.addstr(vpos, hpos, s)
                last_cpu_usage[ee] = cpu_usage
                last_cpu_total[ee] = cpu_total
                vpos+=1
            screen.addstr(vpos, hpos, '')
            screen.refresh()
            sleep(1)

class VNF( SubCmd ):
    "Subcommands for interacting with VNFs."

    prompt = 'mininet:vnf> '

    def __init__( self, mininet, stdin=sys.stdin, script=None ):
        self.mn = mininet
        SubCmd.__init__( self )

    def do_info( self, line ):
        "Print short info about a VNF or all of them if none is specified."
        vnf_catalog = Catalog().get_db()
        for metadata in vnf_catalog.itervalues():
            try:
                if metadata['name'] == line.strip():
                    for k, v in metadata.iteritems():
                        output('%s: %s\n' % (k, v))
                    break
            except KeyError:
                pass
        else:
            for metadata in vnf_catalog.itervalues():
                try:
                    info = metadata.get('description', '').split('\n')[0]
                    output('%s: %s\n' % (metadata['name'], info))
                except KeyError:
                    pass

    def complete_info( self, text, line, begidx, endidx):
        names = Catalog().get_db().keys()
        return [n for n in names if n.startswith(text)]

    def do_reload( self, line):
        "Reload VNF catalog"
        Catalog().load(line)
