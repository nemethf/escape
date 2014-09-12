"""
Helper objects to launch Virtual Network Functions and container managers.
"""
import os
import inspect
import ast
import copy
from mininet.log import error

DB_FILENAME = 'vnfcatalog-old.db.py'


class Catalog( object ):
    """Catalog of VNFs"""
    __shared_state = {}

    def __init__ ( self, filename=None ):
        self.__dict__ = self.__shared_state

        self.db = {}
        self.set_filename(filename)
        self.load()

    def set_filename ( self, filename ):
        if filename:
            self.filename = filename
            return

        this_file = os.path.abspath(inspect.getfile(inspect.currentframe()))
        dirname = os.path.dirname(this_file)
        self.filename = os.path.join(dirname, DB_FILENAME)
        return

    def load ( self, filename=None ):
        if not filename:
            filename = self.filename

        data = []
        try:
            with open(filename) as data_file:
                try:
                    data = ast.literal_eval(data_file.read())
                except SyntaxError as e:
                    error('failed to load catalog from file (%s)\n' % filename)
                    error('error: %s\n' % e)
        except IOError:
            error('failed to load catalog from file (%s)\n' % filename)

        self.db = {}
        for metadata in data:
            try:
                self.db[metadata['name']] = metadata
            except KeyError:
                error('invaild vnf data: %s' % metadata)

    def get_db ( self ):
        "Return the list of metadatas for VNFs available to launch."

        # don't let callers mess with our database
        return copy.deepcopy(self.db)

    def make_cmd ( self, vnf_name, **kw ):
        "Return a command line that starts 'vnf_name'"

        try:
            metadata = copy.deepcopy(self.db[vnf_name])
            vnf_type = metadata['type']
            cls_name = 'Vnf' + vnf_type
            cls = globals()[cls_name]
        except KeyError:
            raise RuntimeError('VNF not found (%s)' % vnf_name)

        metadata.update(kw)
        c = cls()
        return c.make_cmd(**metadata)

class VnfClick( object ):
    """Helper object for convenient launching of click-based vnfs."""

    def __init__( self ):
        pass

    def make_cmd ( self, **kwargs ):
        self.clickCmd = kwargs.get( 'clickCmd', '' )
        self.clickPath = kwargs.get( 'clickPath', '' )
        self.hotConfig = kwargs.get( 'hotConfig', True )
        self.controlSocket = kwargs.get( 'controlSocket', True )
        self.csPort = kwargs.get( 'csPort', 8001 )
        self.vnfName = kwargs.get( 'name', '' )
        self.clickExp = kwargs.get( 'command', '' )
        self.clickFile = kwargs.get( 'clickFile', '' )
        self.output = kwargs.get( 'output', False )
        self.vnfDevs = kwargs.get( 'devs', [] )

        if self.vnfDevs == []:
            # static use-case, single device name is derived from vnf name
            self.vnfDevs = [ self.vnfName + '-eth1' ]

        if self.clickCmd:
            return self.clickCmd + ' &'

        if self.clickPath:
            self.clickCmd = self.clickPath + '/click'
        else:
            self.clickCmd = 'click'

        if self.hotConfig:
            self.clickCmd = self.clickCmd + ' -R'

        if self.controlSocket:
            self.clickCmd = self.clickCmd + ' -p' + str( self.csPort )

        if self.vnfName:
            self.clickCmd = self.clickCmd + ' VNFNAME=' + self.vnfName

        if self.clickFile:
            self.clickCmd = self.clickCmd + ' -f ' + self.clickFile
        else:
            self.clickExp = self.clickExp.replace('\$VNFNAME', self.vnfName)
            for i, dev in enumerate(self.vnfDevs):
                templ = '\$VNFDEV' + str(i)
                self.clickExp = self.clickExp.replace(templ, self.vnfDevs[i])

            self.clickCmd = self.clickCmd + ' -e "' + self.clickExp + '"'

        if self.output:
            return self.clickCmd + ' 2> ' + self.vnfName +'.log &'
        else:
            return self.clickCmd + ' &'


class VnfLookBusy( object ):
    """Helper object for launching complex LookBusy commands."""

    def make_cmd ( self, **kw ):
        "Asseble a complex lookbusy commandline."
        args = ['verbose', 'quiet', 'cpu-util', 'ncpus', 'cpu-mode',
                'cpu-curve-period', 'cpu-curve-peak', 'utc', 'mem-util',
                'mem-sleep', 'disk-util', 'disk-sleep', 'disk-block-size',
                'disk-path']
        cmd = 'lookbusy'
        for k, v in kw.iteritems():
            arg = k.replace('_', '-')
            if arg in args:
                cmd += ' --%s %s' % (arg, v)
            else:
                error( 'lookbusy: unknown argument (%s)\n' % k )
        return cmd + ' &'


class VnfFakeLoad( object ):
    """Helper object for convenient launching of LookBusy."""

    def make_cmd ( self, cpu='', mem='', **kw ):
        """Generate load for testing VNF load balancers."""
        cmd = 'lookbusy'
        if cpu:
            cmd = cmd + ' -c ' + cpu
        if mem:
            cmd = cmd + ' -m ' + mem
        return cmd + ' &'


class VnfNetConf( object ):
    """Helper object for convenient launching of NetConf-based managers."""
    __shared_state = {'start_port': 830}

    def __init__( self, start_port=None ):
        self.__dict__ = self.__shared_state

        if start_port:
            self.start_port = start_port

    def make_cmd ( self, **kwargs ):
        close = kwargs.get( 'close', True )
        cmd = 'netconfd --module=starter --log=/home/unify/mylog'
        cmd += ' --log-level=debug4 --superuser=unify'
        cmd += ' --port=' + str(self.start_port)
        self.start_port += 1

        if close:
            print(cmd + ' &')
            return cmd + ' &'
        else:
            return cmd

