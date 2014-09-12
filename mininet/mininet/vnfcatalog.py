# Copyright (c) 2014 iMinds, BME
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

"""
Helper objects to launch Virtual Network Functions and container managers.
"""
import os
import inspect
import ast
import copy
import sqlite3
from mininet.log import error

# Singleton: not used currently
class Singleton(type):
    _instances = {}
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]

class Catalog( object ):
    """Catalog of VNFs"""
    __shared_state = {}
    # __metaclass__ = Singleton

    def __init__ ( self, filename=None ):
        self.__dict__ = self.__shared_state

        if len(Catalog.__shared_state) == 0:
            self.db = {}
            self.set_filename(filename)
            self.load()

    def set_filename ( self, filename=None ):
        if filename:
            self.filename = filename
            return

        this_file = os.path.abspath(inspect.getfile(inspect.currentframe()))
        dirname = os.path.dirname(this_file)
        self.filename = os.path.join(dirname, 'vnfcatalogue.db')
        return

    def load ( self, filename=None ):

        if not filename:
            filename = self.filename

        self.conn=sqlite3.connect(filename)
        cur=self.conn.cursor()
        cur.execute('''create table if not exists VNFs (name text, type text, description text, command text, readHdr text, writeHdr text, dependency text, icon text, builder_class text, hidden text)''')


        self.db = {}
        data = self.query_db("SELECT * FROM VNFs")

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

    def query_db( self, sql ):

        data = []

        try:
            cur = self.conn.cursor()
            cur.execute(sql)
            column_names = [x[0] for x in cur.description]

            while True:
                row = cur.fetchone()

                if row == None:
                    break
                dictionary = dict(zip(column_names, row))
                data.append(dictionary)

        except  KeyError:

            error( 'Cannot query the Data Base' )

        return data


    def add_VNF(self,**kwargs):

        """ Interface to add new VNF to the Catalog DB """

        vnf_name=kwargs.get('vnf_name','')
        vnf_type=kwargs.get('vnf_type','')

        if self.db.get(vnf_name,''):
            error('VNF %s exists \n' % vnf_name)
            return

        cls_name='Vnf' + vnf_type
        cls = globals()[cls_name]

        c = cls()
        return c.add_VNF(self,**kwargs)


    def remove_VNF(self,**kwargs):

        """ Interface to remove VNF from Catalog DB """

        vnf_name=kwargs.get('vnf_name','')

        # First check the dependencies.
        data=self.query_db("SELECT * FROM VNFs")
        for metadata in data:
            dependency=eval(metadata['dependency'])
            for element in dependency:
                if element==vnf_name:
                    error( "VNF cannot be removed. There is a dependency")
                    return

        del self.db[vnf_name]
        cur=self.conn.cursor()
        name=(vnf_name,)
        cur.execute('DELETE FROM VNFs WHERE name = ?',name)
        self.conn.commit()

    def get_VNF(self, vnf_name):

        """ Interface to get attributes of VNF from Catalog DB given by name  """

        data = []
        name = (vnf_name,)
        sql = "SELECT * FROM VNFs WHERE name = ?"

        try:
            cur = self.conn.cursor()
            cur.execute(sql, name)
            column_names = [x[0] for x in cur.description]

            while True:
                row = cur.fetchone()

                if row == None:
                    break
                dictionary = dict(zip(column_names, row))
                data.append(dictionary)
        except  KeyError:
            error( 'Cannot query the Data Base' )

        return data
    
    
class VnfClick( object ):
    """Helper object for convenient launching of click-based vnfs."""
    # __metaclass__ = Singleton

    def __init__( self ):
        pass

    def make_cmd ( self, **kwargs ):
        self.clickCmd = kwargs.get( 'clickCmd', '' )
        self.clickPath = kwargs.get( 'clickPath', '' )
        self.hotConfig = kwargs.get( 'hotConfig', True )
        self.controlSocket = kwargs.get( 'controlSocket', True )
        self.csPort = kwargs.get( 'csPort', 8001 )
        self.vnfName = kwargs.get( 'name', '' )
        #self.clickExp = kwargs.get( 'command', '' )
        self.clickExp = self.instantiate_VNF(**kwargs)
        self.clickFile = kwargs.get( 'clickFile', '' )
        self.output = kwargs.get( 'output', True )
        #self.mac = kwargs.get( 'mac', '' )

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

        #if self.vnfName:
        #    self.clickCmd = self.clickCmd + ' VNFNAME=' + self.vnfName

        #if self.mac:
        #    self.clickExp = self.clickExp.replace('\$MAC', self.mac)
#             self.clickCmd = self.clickCmd + ' MAC=' + self.mac

        if self.clickFile:
            self.clickCmd = self.clickCmd + ' -f ' + self.clickFile
        else:
        #    self.clickExp = self.clickExp.replace('\$VNFNAME', self.vnfName)
            self.clickCmd = self.clickCmd + ' -e "' + self.clickExp + '"'

        if self.output:
            return self.clickCmd + ' 2> ' + '/tmp/' + self.vnfName + '-' + str(self.csPort) + '.log &'
        else:
            return self.clickCmd + ' &'

    def add_VNF(self,catalog,**kwargs):

        this_file = os.path.abspath(inspect.getfile(inspect.currentframe()))
        dirname = os.path.dirname(this_file)

        self.vnfName = kwargs.get('vnf_name','')
        self.vnfType = kwargs.get('vnf_type','')
        self.clickTempPath = kwargs.get('clickTempPath',dirname+'/templates/'+self.vnfName+'.jinja2')
        self.clickPath = kwargs.get('clickPath','')
        self.clickSource = kwargs.get('clickSource','')
        self.vnfDescription = kwargs.get('description','')
        self.icon = kwargs.get('icon','')
        self.builder_class = kwargs.get('builder_class','VNFClickBuilder')
        self.hidden = kwargs.get('hidden','False')

        #1. First check if the source can be compiled
        if self.clickSource:
            if not self.compile(**kwargs):
                return False


        #2. Check the existence of the required VNFs/Click elements
        dependency=[]

        if os.path.exists(self.clickTempPath):

            with open(self.clickTempPath) as template:

                # It is assumed that elements are defined in the click scripts using "::"
                for line in template:
                    if '::' in line:
                        element=line.split('::')[-1].split('(')[0].replace(' ','')
                        name=(str(element),)
                        cur=catalog.conn.cursor()
                        cur.execute('SELECT * FROM VNFs WHERE name = ?',name)

                        VNF=cur.fetchone()

                        if VNF:
                            dependency.append(str(element))
                        else:
                            error('The new VNF is dependent on non-existing VNF:%s' % element)
                            return False

            template=open(self.clickTempPath,'r').read()
        else:
            template=''

        #3. Extract the Click handlers from the source files (The handlers are used for configuration of VNFs)
        read_handlers={}
        read=[]
        write_handlers={}
        write=[]

        for src in self.clickSource:
            if '.cc' in src:
                with open(self.clickPath+'/'+src) as source:
                    for line in source:
                        if 'add_read_handler' in line:
                            hdlr=line.split('"')[1]
                            if hdlr not in read:
                                read.append(hdlr)

                        if 'add_write_handler' in line:
                            hdlr=line.split('"')[1]
                            if hdlr not in write:
                                write.append(hdlr)

        if read:
            read_handlers[self.vnfName]=read
        if write:
            write_handlers[self.vnfName]=write

        # Add the handlers of other elements used in the Click scripts of the new VNF
        if dependency:
            for element in dependency:
                name=(element,)
                cur=catalog.conn.cursor()
                cur.execute('SELECT * FROM VNFs WHERE name = ?',name)
                VNF=cur.fetchone()

                read=eval(VNF[4]).get(element,'')
                write=eval(VNF[5]).get(element,'')

                if read:

                    read_handlers[element]=read

                if write:

                    write_handlers[element]=write

        #ToDo: the type of the parameters for the handlers should be determined (now only the handlers names are extracted from the source files)

        #4. Add to the DataBase
        cur=catalog.conn.cursor()

        sql = (self.vnfName,
               self.vnfType,
               self.vnfDescription,
               str(template),
               repr(read_handlers),
               repr(write_handlers),
               repr(dependency),
               self.icon,
               self.builder_class,
               self.hidden)
        cur.execute('INSERT INTO VNFs VALUES (?,?,?,?,?,?,?,?,?,?)', sql)
        catalog.conn.commit()

    def instantiate_VNF(self,**kwargs):

        """ Instantiate the VNF (Click script) with the given parameters """

        from jinja2 import Template

        self.clickExp = kwargs.get('command','')

        # all the required parameters for instantiation of the Click scripts should be set here
        self.vnfDevs = kwargs.get('devs', [])
        if self.vnfDevs == []:
            # static use-case, single device name is derived from vnf name
            self.vnfDevs = [ self.vnfName + '-eth1' ]

        self.dev = kwargs.get('device','')
        self.method = kwargs.get( 'method', 'PCAP' )
        self.daddress = kwargs.get( 'daddress', '10.0.0.5' )
        self.interval = kwargs.get( 'interval', '1' )
        self.limit = kwargs.get( 'limit', '-1' )
        self.gw = kwargs.get( 'gw', self.vnfDevs[0] + ':gw' )
        self.mac= kwargs.get('mac','')
        self.public = kwargs.get('public','')

        templateVars = { 'DEV' : self.dev,
                         'METHOD' : self.method,
                         'DADDR' : self.daddress,
                         'INTERVAL' : self.interval,
                         'LIMIT' : self.limit,
                         'GW' : self.gw,
                         'MAC' : self.mac,
                         'public' : self.public }
        for i, dev in enumerate(self.vnfDevs):
            templ = 'VNFDEV' + str(i)
            templateVars[templ] = dev

        template = Template(self.clickExp)
        return template.render(templateVars)
        # return template.render(DEV=self.dev,METHOD=self.method,DADDR=self.daddress,
        #             INTERVAL=self.interval,LIMIT=self.limit,GW=self.gw,
        #             MAC=self.mac,public=self.public)



    def compile(self, **kwargs):

        """ Given the source code of a new Click element, the code is compiled """

        # should be checked!, Currently user level is considered

        # First check if the source files exist
        for src in self.clickSource:
            if not os.path.exists(self.clickPath+'/'+src):
                error('source file does not exist: %s'% src)
                return False


        os.system('cd '+ self.clickPath+'; make clean; ./configure; make elemlist; make' )
        if not os.path.exists(self.clickPath+ '/userlevel/click'):
            error( 'The source code can not be compiled')
            return False
        else:
            print "Successful compile!"
            return True


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
