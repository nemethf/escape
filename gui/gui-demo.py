#!/usr/bin/python
"""
Based on MiniEdit: a simple network editor for Mininet

Bob Lantz, April 2010
Gregory Gee, July 2013

Controller icon from http://semlabs.co.uk/
OpenFlow icon from https://www.opennetworking.org/
"""
import threading
import math
import tkFont
import tkFileDialog
import tkSimpleDialog
import re
import json
import os
import sys
import logging
import Queue
from subprocess import call
from distutils.version import StrictVersion
from PIL import ImageTk, Image
import Utils
from Utils import LoggerHelper
import traceback
import argparse
from collections import namedtuple
import Tkinter as tk
from Tkinter import LabelFrame, Frame, Menu, Canvas, Scrollbar, Label, Entry,\
                    BitmapImage, Button, Wm, Toplevel, \
                    Checkbutton, PanedWindow, \
                    N, E, S, W, NW, EW, Y, FALSE, TRUE,\
                    CENTER, LEFT, RIGHT, SOLID, VERTICAL, BOTH, \
                    TclError, StringVar, IntVar, OptionMenu, \
                    DISABLED, NORMAL, END
import tkMessageBox

from mininet.net import VERSION
from mininet.util import quietRun
from mininet.term import makeTerm, cleanUpScreens
from mininet.node import Controller, RemoteController, NOX, OVSController
from mininet.topo import SingleSwitchTopo, LinearTopo, SingleSwitchReversedTopo
from mininet.topolib import TreeTopo
from mininet.vnfcatalog import Catalog
from mininet import cli

import pox
from pox import core, boot
import networkx

import traffic_steering
import Orchestrator
from Orchestrator import NodeManagerMininetWrapper
from CoreInitListener import CoreInitListener
from NetworkManager import NetworkManagerMininet
from Utils import dump
MINIEDIT_VERSION = '2.1.0.8'

resource_folder = os.path.join("..", "res")
def resource_path(res):
    return os.path.join(resource_folder, res)

if 'PYTHONPATH' in os.environ:
    sys.path = os.environ[ 'PYTHONPATH' ].split( ':' ) + sys.path

TOPODEF = 'none'
TOPOS = { 'minimal': lambda: SingleSwitchTopo( k=2 ),
          'linear': LinearTopo,
          'reversed': SingleSwitchReversedTopo,
          'single': SingleSwitchTopo,
          'none': None,
          'tree': TreeTopo }
CONTROLLERDEF = 'ref'
CONTROLLERS = { 'ref': Controller,
                'ovsc': OVSController,
                'nox': NOX,
                'remote': RemoteController,
                'none': lambda name: None }

TK_COLORS = ['light slate gray', 'dodger blue', 'DarkGoldenrod1', 'dark salmon',
             'pale violet red', 'SteelBlue3', 'cyan4', 'DarkSeaGreen4',
             'green2', 'DarkOliveGreen3', 'cyan', 'IndianRed3',
             'tan2', 'salmon3', 'coral1', 'HotPink1', 'PaleVioletRed2',
             'magenta2', 'MediumOrchid4', 'MediumPurple3', 'gray11']

logging.basicConfig(level=logging.DEBUG,
            format=('%(filename)s: '
                    '%(levelname)s: '
                    '%(funcName)s(): '
                    '%(lineno)d:\t'
                    '%(message)s')
            )

class WidgetLogger(logging.Handler):
    def __init__(self, scheduler, printer, formatter = None):
        logging.Handler.__init__(self)
        self.setLevel(logging.NOTSET)
        self.scheduler = scheduler
        self.printer = printer
        self.formatter = self.format if formatter is None else formatter

    def emit(self, record):
        self.scheduler(self.printer, self.formatter(record))

Tag = namedtuple('Tag', 'name open_tag close_tag settings'.split())

class LogWindow(Frame, LoggerHelper):

    def __init__(self, master):
        Frame.__init__(self, master)
        self.log_messages = ''

        self.tag_configure()

        self.log_text = tk.Text(self, state = DISABLED)
        self.log_text.config(state='disabled')
        [self.log_text.tag_configure(t.name, t.settings) for t in self.tags]

        self.log_pattern = tk.Entry(self)
        self.log_pattern.insert(0, '.*')
        self.parse_pattern()
        self.log_pattern.bind('<Return>', self.parse_pattern)

        #Layout
        self.log_pattern.grid(row = 0, column = 0, sticky = E + W)
        self.log_text.grid(row = 1, column = 0,
                           columnspan = 1,
                           sticky = E + W + N + S)
        self.columnconfigure(0, weight = 1)
        self.rowconfigure(1, weight = 1)

    def tag_configure(self):
        level_t = Tag(name = 'level',
                   open_tag = r'\[l\]',
                   close_tag = r'\[\|l\]',
                   settings = {'foreground':'red'})
        func_t = Tag(name = 'func',
                   open_tag = r'\[f\]',
                   close_tag = r'\[\|f\]',
                   settings = {'foreground':'blue'})
        text_t = Tag(name = 'text',
                   open_tag = r'\[t\]',
                   close_tag = r'\[\|t\]',
                   settings = {'foreground':'black'})

        bold = Tag(name = 'bold',
                   open_tag = r'\[b\]',
                   close_tag  = r'\[\|b\]',
                   settings = {'font':'-weight bold'})

        self.tags = [level_t, func_t, text_t, bold]

    def _is_scroll_needed(self):
        last_visible_char = self.log_text.index('@0,%d' %
                                                self.log_text.winfo_height())
        last_character = self.log_text.index('%s-1c'%END)
        return last_character == last_visible_char

    def log(self, msg):
        #TODO: check it without format characters
        if not self.regex.match(msg): return
        self.log_messages += msg
        self.log_text.config(state=NORMAL)
        need_scroll = self._is_scroll_needed()

        self.log_text.mark_set('INSERT_START', tk.INSERT)
        self.log_text.mark_gravity('INSERT_START', tk.LEFT)
        self.log_text.insert(tk.END, msg)

        for tag in self.tags:
            msg = self.log_text.get('INSERT_START',tk.INSERT)
            str_l = len(msg)
            search_pattern = r'%s(.*?)%s'%(tag.open_tag, tag.close_tag)
            for e in re.finditer(search_pattern, msg):
                text_start = e.start(1)
                text_end = e.end(1)
                self.log_text.tag_add(tag.name,
                                      '%s - %dc'%(tk.INSERT, str_l-text_start),
                                      '%s-%dc'%(tk.INSERT, str_l-text_end))

                self.log_text.delete('%s-%dc'%(tk.INSERT, str_l-e.start()),
                                     '%s-%dc'%(tk.INSERT, str_l-text_start))
                #remove close tag
                self.log_text.delete('%s-%dc'%(tk.INSERT, str_l-text_end),
                                     '%s-%dc'%(tk.INSERT, str_l-e.end()))

        self.log_text.mark_unset('INSERT_START')

        if need_scroll: self.log_text.see(END)  # Scroll to the bottom

        self.log_text.config(state='disabled')
        self.update_idletasks()

    def reload_logs(self):
        self.log_text.config(state=NORMAL)
        self.log_text.delete('1.0', tk.END)
        self.log_text.config(state=DISABLED)
        for line in self.log_messages.splitlines(True):
            self.log(line)

    def parse_pattern(self, *args):
        pattern = self.log_pattern.get()
        if not pattern: pattern = '.*'
        self.regex = re.compile(pattern, re.MULTILINE)
        self._debug('change log regex to %s' % pattern)
        self.reload_logs()

# Edit menu -> Preferences
class PrefsDialog(tkSimpleDialog.Dialog):

        def __init__(self, parent, title, prefDefaults):

            self.prefValues = prefDefaults

            tkSimpleDialog.Dialog.__init__(self, parent, title)

        def body(self, master):
            self.rootFrame = master
            self.leftfieldFrame = Frame(self.rootFrame, padx=5, pady=5)
            self.leftfieldFrame.grid(row=0, column=0, sticky='nswe', columnspan=2)
            self.rightfieldFrame = Frame(self.rootFrame, padx=5, pady=5)
            self.rightfieldFrame.grid(row=0, column=2, sticky='nswe', columnspan=2)


            # Field for Base IP
            Label(self.leftfieldFrame, text="IP Base:").grid(row=0, sticky=E)
            self.ipEntry = Entry(self.leftfieldFrame)
            self.ipEntry.grid(row=0, column=1)
            ipBase =  self.prefValues['ipBase']
            self.ipEntry.insert(0, ipBase)

            # Selection of terminal type
            Label(self.leftfieldFrame, text="Default Terminal:").grid(row=1, sticky=E)
            self.terminalVar = StringVar(self.leftfieldFrame)
            self.terminalOption = OptionMenu(self.leftfieldFrame, self.terminalVar, "xterm", "gterm")
            self.terminalOption.grid(row=1, column=1, sticky=W)
            terminalType = self.prefValues['terminalType']
            self.terminalVar.set(terminalType)

            # Field for CLI
            Label(self.leftfieldFrame, text="Start CLI:").grid(row=2, sticky=E)
            self.cliStart = IntVar()
            self.cliButton = Checkbutton(self.leftfieldFrame, variable=self.cliStart)
            self.cliButton.grid(row=2, column=1, sticky=W)
            if self.prefValues['startCLI'] == '0':
                self.cliButton.deselect()
            else:
                self.cliButton.select()

            # Selection of switch type
            Label(self.leftfieldFrame, text="Default Switch:").grid(row=3, sticky=E)
            self.switchType = StringVar(self.leftfieldFrame)
            self.switchTypeMenu = OptionMenu(self.leftfieldFrame, self.switchType, "Open vSwitch", "Indigo Virtual Switch", "Userspace Switch", "Userspace Switch inNamespace")
            self.switchTypeMenu.grid(row=3, column=1, sticky=W)
            switchTypePref = self.prefValues['switchType']
            if switchTypePref == 'ivs':
                self.switchType.set("Indigo Virtual Switch")
            elif switchTypePref == 'userns':
                self.switchType.set("Userspace Switch inNamespace")
            elif switchTypePref == 'user':
                self.switchType.set("Userspace Switch")
            else:
                self.switchType.set("Open vSwitch")


            # Fields for OVS OpenFlow version
            ovsFrame= LabelFrame(self.leftfieldFrame, text='Open vSwitch', padx=5, pady=5)
            ovsFrame.grid(row=4, column=0, columnspan=2, sticky=EW)
            Label(ovsFrame, text="OpenFlow 1.0:").grid(row=0, sticky=E)
            Label(ovsFrame, text="OpenFlow 1.1:").grid(row=1, sticky=E)
            Label(ovsFrame, text="OpenFlow 1.2:").grid(row=2, sticky=E)
            Label(ovsFrame, text="OpenFlow 1.3:").grid(row=3, sticky=E)

            self.ovsOf10 = IntVar()
            self.covsOf10 = Checkbutton(ovsFrame, variable=self.ovsOf10)
            self.covsOf10.grid(row=0, column=1, sticky=W)
            if self.prefValues['openFlowVersions']['ovsOf10'] == '0':
                self.covsOf10.deselect()
            else:
                self.covsOf10.select()

            self.ovsOf11 = IntVar()
            self.covsOf11 = Checkbutton(ovsFrame, variable=self.ovsOf11)
            self.covsOf11.grid(row=1, column=1, sticky=W)
            if self.prefValues['openFlowVersions']['ovsOf11'] == '0':
                self.covsOf11.deselect()
            else:
                self.covsOf11.select()

            self.ovsOf12 = IntVar()
            self.covsOf12 = Checkbutton(ovsFrame, variable=self.ovsOf12)
            self.covsOf12.grid(row=2, column=1, sticky=W)
            if self.prefValues['openFlowVersions']['ovsOf12'] == '0':
                self.covsOf12.deselect()
            else:
                self.covsOf12.select()

            self.ovsOf13 = IntVar()
            self.covsOf13 = Checkbutton(ovsFrame, variable=self.ovsOf13)
            self.covsOf13.grid(row=3, column=1, sticky=W)
            if self.prefValues['openFlowVersions']['ovsOf13'] == '0':
                self.covsOf13.deselect()
            else:
                self.covsOf13.select()

            # Field for DPCTL listen port
            Label(self.leftfieldFrame, text="dpctl port:").grid(row=5, sticky=E)
            self.dpctlEntry = Entry(self.leftfieldFrame)
            self.dpctlEntry.grid(row=5, column=1)
            if 'dpctl' in self.prefValues:
                self.dpctlEntry.insert(0, self.prefValues['dpctl'])

            # sFlow
            sflowValues = self.prefValues['sflow']
            self.sflowFrame= LabelFrame(self.rightfieldFrame, text='sFlow Profile for Open vSwitch', padx=5, pady=5)
            self.sflowFrame.grid(row=0, column=0, columnspan=2, sticky=EW)

            Label(self.sflowFrame, text="Target:").grid(row=0, sticky=E)
            self.sflowTarget = Entry(self.sflowFrame)
            self.sflowTarget.grid(row=0, column=1)
            self.sflowTarget.insert(0, sflowValues['sflowTarget'])

            Label(self.sflowFrame, text="Sampling:").grid(row=1, sticky=E)
            self.sflowSampling = Entry(self.sflowFrame)
            self.sflowSampling.grid(row=1, column=1)
            self.sflowSampling.insert(0, sflowValues['sflowSampling'])

            Label(self.sflowFrame, text="Header:").grid(row=2, sticky=E)
            self.sflowHeader = Entry(self.sflowFrame)
            self.sflowHeader.grid(row=2, column=1)
            self.sflowHeader.insert(0, sflowValues['sflowHeader'])

            Label(self.sflowFrame, text="Polling:").grid(row=3, sticky=E)
            self.sflowPolling = Entry(self.sflowFrame)
            self.sflowPolling.grid(row=3, column=1)
            self.sflowPolling.insert(0, sflowValues['sflowPolling'])

            # NetFlow
            nflowValues = self.prefValues['netflow']
            self.nFrame= LabelFrame(self.rightfieldFrame, text='NetFlow Profile for Open vSwitch', padx=5, pady=5)
            self.nFrame.grid(row=1, column=0, columnspan=2, sticky=EW)

            Label(self.nFrame, text="Target:").grid(row=0, sticky=E)
            self.nflowTarget = Entry(self.nFrame)
            self.nflowTarget.grid(row=0, column=1)
            self.nflowTarget.insert(0, nflowValues['nflowTarget'])

            Label(self.nFrame, text="Active Timeout:").grid(row=1, sticky=E)
            self.nflowTimeout = Entry(self.nFrame)
            self.nflowTimeout.grid(row=1, column=1)
            self.nflowTimeout.insert(0, nflowValues['nflowTimeout'])

            Label(self.nFrame, text="Add ID to Interface:").grid(row=2, sticky=E)
            self.nflowAddId = IntVar()
            self.nflowAddIdButton = Checkbutton(self.nFrame, variable=self.nflowAddId)
            self.nflowAddIdButton.grid(row=2, column=1, sticky=W)
            if nflowValues['nflowAddId'] == '0':
                self.nflowAddIdButton.deselect()
            else:
                self.nflowAddIdButton.select()

            # initial focus
            return self.ipEntry

        def apply(self):
            ipBase = self.ipEntry.get()
            terminalType = self.terminalVar.get()
            startCLI = str(self.cliStart.get())
            sw = self.switchType.get()
            dpctl = self.dpctlEntry.get()

            ovsOf10 = str(self.ovsOf10.get())
            ovsOf11 = str(self.ovsOf11.get())
            ovsOf12 = str(self.ovsOf12.get())
            ovsOf13 = str(self.ovsOf13.get())

            sflowValues = {'sflowTarget':self.sflowTarget.get(),
                           'sflowSampling':self.sflowSampling.get(),
                           'sflowHeader':self.sflowHeader.get(),
                           'sflowPolling':self.sflowPolling.get()}
            nflowvalues = {'nflowTarget':self.nflowTarget.get(),
                           'nflowTimeout':self.nflowTimeout.get(),
                           'nflowAddId':str(self.nflowAddId.get())}
            self.result = {'ipBase':ipBase,
                           'terminalType':terminalType,
                           'dpctl':dpctl,
                           'sflow':sflowValues,
                           'netflow':nflowvalues,
                           'startCLI':startCLI}
            if sw == 'Indigo Virtual Switch':
                self.result['switchType'] = 'ivs'
                if StrictVersion(VERSION) < StrictVersion('2.1'):
                    self.ovsOk = False
                    tkMessageBox.showerror(title="Error",
                              message='MiniNet version 2.1+ required. You have '+VERSION+'.')
            elif sw == 'Userspace Switch':
                self.result['switchType'] = 'user'
            elif sw == 'Userspace Switch inNamespace':
                self.result['switchType'] = 'userns'
            else:
                self.result['switchType'] = 'ovs'

            self.ovsOk = True
            if ovsOf11 == "1":
                ovsVer = self.getOvsVersion()
                if StrictVersion(ovsVer) < StrictVersion('2.0'):
                    self.ovsOk = False
                    tkMessageBox.showerror(title="Error",
                              message='Open vSwitch version 2.0+ required. You have '+ovsVer+'.')
            if ovsOf12 == "1" or ovsOf13 == "1":
                ovsVer = self.getOvsVersion()
                if StrictVersion(ovsVer) < StrictVersion('1.10'):
                    self.ovsOk = False
                    tkMessageBox.showerror(title="Error",
                              message='Open vSwitch version 1.10+ required. You have '+ovsVer+'.')

            if self.ovsOk:
                self.result['openFlowVersions']={'ovsOf10':ovsOf10,
                                                 'ovsOf11':ovsOf11,
                                                 'ovsOf12':ovsOf12,
                                                 'ovsOf13':ovsOf13}
            else:
                self.result = None

        def getOvsVersion(self):
            outp = quietRun("ovs-vsctl show")
            r = r'ovs_version: "(.*)"'
            m = re.search(r, outp)
            if m is None:
                print 'Version check failed'
                return None
            else:
                print 'Open vSwitch version is '+m.group(1)
                return m.group(1)

# Superclass for Properties Dialog
class CustomDialog(object):

        # TODO: Fix button placement and Title and window focus lock
        def __init__(self, master, title):
            self.top=Toplevel(master)
            self.master = master
            self.opt = {}

            # Set defaults from 'req' and 'res'
            # (TODO: what if a property is defined in both categories?)
            for category in ['req', 'res']:
                try:
                    for k,v in self.prefValues.get(category, {}).iteritems():
                        if not self.prefValues.get(k):
                            self.prefValues[k] = v
                except AttributeError:
                    pass

            self.bodyFrame = Frame(self.top)
            self.bodyFrame.grid(row=0, column=0, sticky='nswe')
            self.body(self.bodyFrame)

            #return self.b # initial focus
            buttonFrame = Frame(self.top, relief='ridge', bd=3, bg='lightgrey')
            buttonFrame.grid(row=1 , column=0, sticky='nswe')

            okButton = Button(buttonFrame, width=8, text='OK', relief='groove',
                       bd=4, command=self.okAction)
            okButton.grid(row=0, column=0, sticky=E)

            canlceButton = Button(buttonFrame, width=8, text='Cancel', relief='groove',
                        bd=4, command=self.cancelAction)
            canlceButton.grid(row=0, column=1, sticky=W)

        def body(self, master):
            # create dialog body.  return widget that should have initial focus.  this method should be overridden
            self.rootFrame = master

        def apply(self):
            # invoked if OK button pressed
            self.top.destroy()

        def cancelAction(self):
            self.top.destroy()

        def okAction(self):
            self.apply()
            self.top.destroy()

        def addFrames(self, master, root=True):
            if root:
                self.rootFrame = master
            l = Frame(master)
            r = Frame(master)
            l.grid(row=0, column=0, sticky='nswe', columnspan=2)
            r.grid(row=0, column=2, sticky='nswe', columnspan=2)

            master.field_frames = [l, r]
            master.next_col = 0
            master.next_row = 0

        def nextPosInFrames(self, rootFrame=None):
            if not rootFrame:
                rootFrame = self.rootFrame
            col = rootFrame.next_col
            row = rootFrame.next_row
            frame = rootFrame.field_frames[col]

            rootFrame.next_col = (col + 1) % 2
            rootFrame.next_row = row + ((col + 1) / 2)

            return col, row, frame

        def addField(self, name, opt_name,
                     rootFrame=None, tooltip=None):
            if not rootFrame:
                rootFrame = self.rootFrame

            value = self.prefValues.get(opt_name, '')
            col, row, frame = self.nextPosInFrames(rootFrame)

            l = Label(frame, text=name)
            e = Entry(frame)
            l.grid(row=row, sticky=E)
            e.grid(row=row, column=1)
            e.insert(0, str(value))
            self.opt[opt_name] = e
            if tooltip:
                self.master.createToolTip(l, tooltip)
                self.master.createToolTip(e, tooltip)

        def addOptionField(self, name, opt_name, opts, trace=None):
            value = self.prefValues.get(opt_name, opts[0])
            col, row, frame = self.nextPosInFrames()

            Label(frame, text=name).grid(row=row, sticky=E)
            var = StringVar(frame)
            var.set(value)
            menu = OptionMenu(frame, var, *opts)
            menu.grid(row=row, column=1, sticky=W)
            self.opt[opt_name] = var
            if trace:
                var.trace('w', trace)

# Container element -> Properties
class HostDialog(CustomDialog):

        def __init__(self, master, title, prefDefaults):
            self.prefValues = prefDefaults
            self.result = {}
            CustomDialog.__init__(self, master, title)

        def body(self, master):
            self.addFrames(master)
            self.ee_types = ['static', 'netconf', 'remote']
            self.addField('Name:', 'hostname')
            self.addField('Cpu capacity:', 'cpu')
            self.addField('IP Address:', 'ip')
            self.addField('Memory capacity:', 'mem')
            self.addField('Default Route:', 'defaultRoute')
            self.addField("Cores:", 'cores')
            self.addOptionField("Type:", 'ee_type',
                                self.ee_types, trace=self._on_change)
            self.addOptionField("Scheduler:", 'sched',
                                ['host', 'cfs', 'rt'])

            self.dynamicFrames = {}
            self.current_dframe = None
            self.current_ee_type = None
            for t in self.ee_types:
                d = Frame(self.rootFrame)
                self.dynamicFrames[t] = d
                attr = getattr(self, 'body_' + t)
                attr(d)
            self.show_dynamic_frame(self.opt.get('ee_type').get())

        def show_dynamic_frame(self, ee_type):
            # hide the currently visible
            if ee_type == self.current_ee_type:
                return
            if self.current_dframe:
                self.current_dframe.grid_forget()

            f = self.dynamicFrames[ee_type]
            f.grid(row=1, column=0, columnspan=4, sticky='nswe')
            self.current_dframe = f
            self.current_ee_type = ee_type

        def _on_change( self, *args ):
            new_ee_type = self.opt.get('ee_type').get()
            self.show_dynamic_frame(new_ee_type)

        def body_static(self, frame):

            # External Interfaces
            self.externalInterfaces = 0
            Label(frame, text="External Interface:").grid(row=1, column=0, sticky=E)
            self.b = Button( frame, text='Add', command=self.addInterface)
            self.b.grid(row=1, column=1)

            self.interfaceFrame = VerticalScrolledTable(frame, rows=0, columns=1, title='External Interfaces')
            self.interfaceFrame.grid(row=2, column=0, sticky='nswe', columnspan=2)
            self.tableFrame = self.interfaceFrame.interior
            self.tableFrame.addRow(value=['Interface Name'], readonly=True)

            # Add defined interfaces
            externalInterfaces = self.prefValues.get('externalInterfaces', [])

            for externalInterface in externalInterfaces:
                self.tableFrame.addRow(value=[externalInterface])

            # VLAN Interfaces
            self.vlanInterfaces = 0
            Label(frame, text="VLAN Interface:").grid(row=1, column=2, sticky=E)
            self.vlanButton = Button( frame, text='Add', command=self.addVlanInterface)
            self.vlanButton.grid(row=1, column=3)

            self.vlanFrame = VerticalScrolledTable(frame, rows=0, columns=2, title='VLAN Interfaces')
            self.vlanFrame.grid(row=2, column=2, sticky='nswe', columnspan=2)
            self.vlanTableFrame = self.vlanFrame.interior
            self.vlanTableFrame.addRow(value=['IP Address','VLAN ID'], readonly=True)

            vlanInterfaces = []
            if 'vlanInterfaces' in self.prefValues:
                vlanInterfaces = self.prefValues['vlanInterfaces']
            for vlanInterface in vlanInterfaces:
                self.vlanTableFrame.addRow(value=vlanInterface)

        def body_netconf( self, frame ):
            Label(frame, text='netconf').grid(row=0, sticky='nswe')

        def body_remote( self, frame ):
            f = frame
            self.addFrames(f, root = False)
            self.addField('Remote DPID:', 'remote_dpid', f,
                          'DPID of the remote switch. E.g., 0015ab5f2d01')
            self.addField('Remote port:', 'remote_port', f,
                          'Port number of the remote sw where '
                          + 'the local interface is connected to')
            self.addField('Remote conf IP:', 'remote_conf_ip', f,
                          'the IP where the netconf agent can be reached.'
                          + ' E.g., 10.0.0.1')
            self.addField('Remote netconf port:', 'remote_netconf_port', f,
                          'The TCP port where netconf listens to. E.g., 830')
            self.addField('netconf username:', 'netconf_username', f)
            self.addField('netconf passwd:', 'netconf_passwd', f)
            self.addField('Local intf name:', 'local_intf_name', f,
                          'the interface that are connected to the remote sw. '
                          + 'E.g., eth0')

        def addVlanInterface( self ):
            self.vlanTableFrame.addRow()

        def addInterface( self ):
            self.tableFrame.addRow()

        def apply(self):
#             externalInterfaces = []
#             for row in range(self.tableFrame.rows):
#                 if (len(self.tableFrame.get(row, 0)) > 0 and
#                     row > 0):
#                     externalInterfaces.append(self.tableFrame.get(row, 0))
#             vlanInterfaces = []
#             for row in range(self.vlanTableFrame.rows):
#                 if (len(self.vlanTableFrame.get(row, 0)) > 0 and
#                     len(self.vlanTableFrame.get(row, 1)) > 0 and
#                     row > 0):
#                     vlanInterfaces.append([self.vlanTableFrame.get(row, 0), self.vlanTableFrame.get(row, 1)])

            for o in ['hostname', 'sched', 'ee_type',
                      'remote_dpid', 'remote_port', 'remote_conf_ip',
                      'remote_netconf_port', 'netconf_username',
                      'netconf_passwd', 'local_intf_name']:
                var = self.opt.get(o)
                if var:
                    self.result[o] = var.get()
                else:
                    self.result[o] = ''
            
            if 'res' not in self.result:
                self.result['res'] = dict()
            for o in ['mem', 'cpu']:
                var = self.opt.get(o)
                if var:
                    self.result['res'][o] = var.get()
                else:
                    self.result['res'][o] = ''

# VNF element -> Properties
class VnfDialog(CustomDialog):

        def __init__(self, master, title, prefDefaults):
            self.prefValues = prefDefaults
            self.result = {}
            CustomDialog.__init__(self, master, title)

        def body(self, master):
            self.addFrames(master)

            vnf_db = Catalog().get_db()
            # methods = [ v['name'] for v in vnf_db.itervalues() ]
            methods = []
            for v in vnf_db.itervalues():
                if v['hidden'] not in ['true', 'True', 'yes', 'Yes']:
                    # add VNF to the list only if it is not hidden
                    methods.append(v['name'])

            methods.sort()

            self.addField('Name:', 'name')
            self.addOptionField('Start command:', 'function', methods)
            self.addField('CPU needed:', 'cpu')
            self.addField('Memory need:', 'mem')

        def apply(self):
            for o in ['name', 'function', 'mem', 'cpu']:
                self.result[o] = self.opt.get(o).get()

# SAP element -> Properties
class StartpointDialog(CustomDialog):

        def __init__(self, master, title, prefDefaults):
            self.prefValues = prefDefaults
            self.result = {}
            CustomDialog.__init__(self, master, title)

        def body(self, master):
            self.addFrames(master)
            self.addField('Name:', 'name')

        def apply(self):
            for o in ['name']:
                self.result[o] = self.opt.get(o).get()

# OF switch element -> Properties
class SwitchDialog(CustomDialog):

        def __init__(self, master, title, prefDefaults):
            self.prefValues = prefDefaults
            self.result = None
            CustomDialog.__init__(self, master, title)

        def body(self, master):
            self.rootFrame = master
            rowCount = 0
            externalInterfaces = []
            if 'externalInterfaces' in self.prefValues:
                externalInterfaces = self.prefValues['externalInterfaces']

            self.fieldFrame = Frame(self.rootFrame)
            self.fieldFrame.grid(row=0, column=0, sticky='nswe')

            # Field for Hostname
            Label(self.fieldFrame, text="Hostname:").grid(row=rowCount, sticky=E)
            self.hostnameEntry = Entry(self.fieldFrame)
            self.hostnameEntry.grid(row=rowCount, column=1)
            self.hostnameEntry.insert(0, self.prefValues['hostname'])
            rowCount+=1

            # Field for DPID
            Label(self.fieldFrame, text="DPID:").grid(row=rowCount, sticky=E)
            self.dpidEntry = Entry(self.fieldFrame)
            self.dpidEntry.grid(row=rowCount, column=1)
            if 'dpid' in self.prefValues:
                self.dpidEntry.insert(0, self.prefValues['dpid'])
            rowCount+=1

            # Field for Netflow
            Label(self.fieldFrame, text="Enable NetFlow:").grid(row=rowCount, sticky=E)
            self.nflow = IntVar()
            self.nflowButton = Checkbutton(self.fieldFrame, variable=self.nflow)
            self.nflowButton.grid(row=rowCount, column=1, sticky=W)
            if 'netflow' in self.prefValues:
                if self.prefValues['netflow'] == '0':
                    self.nflowButton.deselect()
                else:
                    self.nflowButton.select()
            else:
                self.nflowButton.deselect()
            rowCount+=1

            # Field for sflow
            Label(self.fieldFrame, text="Enable sFlow:").grid(row=rowCount, sticky=E)
            self.sflow = IntVar()
            self.sflowButton = Checkbutton(self.fieldFrame, variable=self.sflow)
            self.sflowButton.grid(row=rowCount, column=1, sticky=W)
            if 'sflow' in self.prefValues:
                if self.prefValues['sflow'] == '0':
                    self.sflowButton.deselect()
                else:
                    self.sflowButton.select()
            else:
                self.sflowButton.deselect()
            rowCount+=1

            # Selection of switch type
            Label(self.fieldFrame, text="Switch Type:").grid(row=rowCount, sticky=E)
            
            self.switchType = StringVar(self.fieldFrame)
            
            self.switchTypeMenu = OptionMenu(self.fieldFrame, self.switchType, "Default", "Open vSwitch", "Indigo Virtual Switch", "Userspace Switch", "Userspace Switch inNamespace")
            self.switchTypeMenu.grid(row=rowCount, column=1, sticky=W)
            if 'switchType' in self.prefValues:
                switchTypePref = self.prefValues['switchType']
                if switchTypePref == 'ivs':
                    self.switchType.set("Indigo Virtual Switch")
                elif switchTypePref == 'userns':
                    self.switchType.set("Userspace Switch inNamespace")
                elif switchTypePref == 'user':
                    self.switchType.set("Userspace Switch")
                elif switchTypePref == 'ovs':
                    self.switchType.set("Open vSwitch")
                else:
                    self.switchType.set("Default")
            else:
                self.switchType.set("Default")
            rowCount+=1

            # Field for Switch IP
            Label(self.fieldFrame, text="IP Address:").grid(row=rowCount, sticky=E)
            
            self.ipEntry = Entry(self.fieldFrame)
            self.ipEntry.grid(row=rowCount, column=1)
            if 'switchIP' in self.prefValues:
                self.ipEntry.insert(0, self.prefValues['switchIP'])
            rowCount+=1

            # Field for DPCTL port
            Label(self.fieldFrame, text="DPCTL port:").grid(row=rowCount, sticky=E)
            
            self.dpctlEntry = Entry(self.fieldFrame)
            self.dpctlEntry.grid(row=rowCount, column=1)
            if 'dpctl' in self.prefValues:
                self.dpctlEntry.insert(0, self.prefValues['dpctl'])
            rowCount+=1

            # External Interfaces
            Label(self.fieldFrame, text="External Interface:").grid(row=rowCount, sticky=E)
            
            self.b = Button( self.fieldFrame, text='Add', command=self.addInterface)
            self.b.grid(row=rowCount, column=1)

            
            self.interfaceFrame = VerticalScrolledTable(self.rootFrame, rows=0, columns=1, title='External Interfaces')
            self.interfaceFrame.grid(row=2, column=0, sticky='nswe')
            
            self.tableFrame = self.interfaceFrame.interior

            # Add defined interfaces
            for externalInterface in externalInterfaces:
                self.tableFrame.addRow(value=[externalInterface])
            rowCount+=1

        def addInterface( self ):
            self.tableFrame.addRow()

        
        def defaultDpid( self ,name):
            """Derive dpid from switch name, s1 -> 1"""
            try:
                dpid = int( re.findall( r'\d+', name )[ 0 ] )
                dpid = hex( dpid )[ 2: ]
                return dpid
            except IndexError:
                return None
                #raise Exception( 'Unable to derive default datapath ID - '
                #                 'please either specify a dpid or use a '
                #                 'canonical switch name such as s23.' )

        def apply(self):
            externalInterfaces = []
            for row in range(self.tableFrame.rows):
                #print 'Interface is ' + self.tableFrame.get(row, 0)
                if len(self.tableFrame.get(row, 0)) > 0:
                    externalInterfaces.append(self.tableFrame.get(row, 0))

            dpid = self.dpidEntry.get()
            if (self.defaultDpid(self.hostnameEntry.get()) is None
               and len(dpid) == 0):
                tkMessageBox.showerror(title="Error",
                              message= 'Unable to derive default datapath ID - '
                                 'please either specify a DPID or use a '
                                 'canonical switch name such as s23.' )


            results = {'externalInterfaces':externalInterfaces,
                       'hostname':self.hostnameEntry.get(),
                       'dpid':dpid,
                       'sflow':str(self.sflow.get()),
                       'netflow':str(self.nflow.get()),
                       'dpctl':self.dpctlEntry.get(),
                       'switchIP':self.ipEntry.get()}
            sw = self.switchType.get()
            if sw == 'Indigo Virtual Switch':
                results['switchType'] = 'ivs'
            elif sw == 'Userspace Switch inNamespace':
                results['switchType'] = 'userns'
            elif sw == 'Userspace Switch':
                results['switchType'] = 'user'
            elif sw == 'Open vSwitch':
                results['switchType'] = 'ovs'
            else:
                results['switchType'] = 'default'
            self.result = results

# Representation feature
class VerticalScrolledTable(LabelFrame):
    """A pure Tkinter scrollable frame that actually works!

    * Use the 'interior' attribute to place widgets inside the scrollable frame
    * Construct and pack/place/grid normally
    * This frame only allows vertical scrolling

    """
    def __init__(self, parent, rows=2, columns=2, title=None, *args, **kw):
        LabelFrame.__init__(self, parent, text=title, padx=5, pady=5, *args, **kw)

        # create a canvas object and a vertical scrollbar for scrolling it
        vscrollbar = Scrollbar(self, orient=VERTICAL)
        vscrollbar.pack(fill=Y, side=RIGHT, expand=FALSE)
        canvas = Canvas(self, bd=0, highlightthickness=0,
                        yscrollcommand=vscrollbar.set)
        canvas.pack(side=LEFT, fill=BOTH, expand=TRUE)
        vscrollbar.config(command=canvas.yview)

        # reset the view
        canvas.xview_moveto(0)
        canvas.yview_moveto(0)


        # create a frame inside the canvas which will be scrolled with it
        self.interior = interior = TableFrame(canvas, rows=rows, columns=columns)
        interior_id = canvas.create_window(0, 0, window=interior,
                                           anchor=NW)

        # track changes to the canvas and frame width and sync them,
        # also updating the scrollbar
        
        def _configure_interior(event):
            # update the scrollbars to match the size of the inner frame
            size = (interior.winfo_reqwidth(), interior.winfo_reqheight())
            canvas.config(scrollregion="0 0 %s %s" % size)
            if interior.winfo_reqwidth() != canvas.winfo_width():
                # update the canvas's width to fit the inner frame
                canvas.config(width=interior.winfo_reqwidth())
        interior.bind('<Configure>', _configure_interior)

        
        def _configure_canvas(event):
            if interior.winfo_reqwidth() != canvas.winfo_width():
                # update the inner frame's width to fill the canvas
                canvas.itemconfigure(interior_id, width=canvas.winfo_width())
        canvas.bind('<Configure>', _configure_canvas)

        return

# Representation feature
class TableFrame(Frame):
    def __init__(self, parent, rows=2, columns=2):

        Frame.__init__(self, parent, background="black")
        self._widgets = []
        self.rows = rows
        self.columns = columns
        for row in range(rows):
            current_row = []
            for column in range(columns):
                label = Entry(self, borderwidth=0)
                label.grid(row=row, column=column, sticky="wens", padx=1, pady=1)
                current_row.append(label)
            self._widgets.append(current_row)

    def set(self, row, column, value):
        widget = self._widgets[row][column]
        widget.insert(0, value)

    def get(self, row, column):
        widget = self._widgets[row][column]
        return widget.get()

    def addRow( self, value=None, readonly=False ):
        #print "Adding row " + str(self.rows +1)
        current_row = []
        for column in range(self.columns):
            label = Entry(self, borderwidth=0)
            label.grid(row=self.rows, column=column, sticky="wens", padx=1, pady=1)
            if value is not None:
                label.insert(0, value[column])
            if readonly:
                label.configure(state='readonly')
            current_row.append(label)
        self._widgets.append(current_row)
        self.update_idletasks()
        self.rows += 1

# Link element -> Properties
class LinkDialog(tkSimpleDialog.Dialog):

        def __init__(self, parent, title, linkDefaults):

            self.linkValues = linkDefaults

            tkSimpleDialog.Dialog.__init__(self, parent, title)

        def body(self, master):

            
            self.var = StringVar(master)
            Label(master, text="Bandwidth:").grid(row=0, sticky=E)
            
            self.e1 = Entry(master)
            self.e1.grid(row=0, column=1)
            Label(master, text="Mbit").grid(row=0, column=2, sticky=W)
            if 'bw' in self.linkValues:
                self.e1.insert(0,str(self.linkValues['bw']))

            Label(master, text="Delay:").grid(row=1, sticky=E)
            
            self.e2 = Entry(master)
            self.e2.grid(row=1, column=1)
            Label(master, text="ms").grid(row=1, column=2, sticky=W)
            if 'delay' in self.linkValues:
                self.e2.insert(0, self.linkValues['delay'])

            Label(master, text="Loss:").grid(row=2, sticky=E)
            
            self.e3 = Entry(master)
            self.e3.grid(row=2, column=1)
            Label(master, text="%").grid(row=2, column=2, sticky=W)
            if 'loss' in self.linkValues:
                self.e3.insert(0, str(self.linkValues['loss']))

            Label(master, text="Max Queue size:").grid(row=3, sticky=E)
            
            self.e4 = Entry(master)
            self.e4.grid(row=3, column=1)
            if 'max_queue_size' in self.linkValues:
                self.e4.insert(0, str(self.linkValues['max_queue_size']))

            Label(master, text="Jitter:").grid(row=4, sticky=E)
            
            self.e5 = Entry(master)
            self.e5.grid(row=4, column=1)
            if 'jitter' in self.linkValues:
                self.e5.insert(0, self.linkValues['jitter'])

            Label(master, text="Speedup:").grid(row=5, sticky=E)
            
            self.e6 = Entry(master)
            self.e6.grid(row=5, column=1)
            if 'speedup' in self.linkValues:
                self.e6.insert(0, str(self.linkValues['speedup']))

            return self.e1 # initial focus

        def apply(self):
            self.result = {}
            if len(self.e1.get()) > 0:
                self.result['bw'] = int(self.e1.get())
            if len(self.e2.get()) > 0:
                self.result['delay'] = float(self.e2.get())
            if len(self.e3.get()) > 0:
                self.result['loss'] = int(self.e3.get())
            if len(self.e4.get()) > 0:
                self.result['max_queue_size'] = int(self.e4.get())
            if len(self.e5.get()) > 0:
                self.result['jitter'] = float(self.e5.get())
            if len(self.e6.get()) > 0:
                self.result['speedup'] = int(self.e6.get())

# Controller element -> Properties
class ControllerDialog(tkSimpleDialog.Dialog):

        def __init__(self, parent, title, ctrlrDefaults=None):

            if ctrlrDefaults:
                self.ctrlrValues = ctrlrDefaults

            tkSimpleDialog.Dialog.__init__(self, parent, title)

        def body(self, master):

            
            self.var = StringVar(master)

            rowCount=0
            # Field for Hostname
            Label(master, text="Name:").grid(row=rowCount, sticky=E)
            
            self.hostnameEntry = Entry(master)
            self.hostnameEntry.grid(row=rowCount, column=1)
            self.hostnameEntry.insert(0, self.ctrlrValues['hostname'])
            rowCount+=1

            # Field for Remove Controller Port
            Label(master, text="Controller Port:").grid(row=rowCount, sticky=E)
            
            self.e2 = Entry(master)
            self.e2.grid(row=rowCount, column=1)
            self.e2.insert(0, self.ctrlrValues['remotePort'])
            rowCount+=1

            # Field for Controller Type
            Label(master, text="Controller Type:").grid(row=rowCount, sticky=E)
            controllerType = self.ctrlrValues['controllerType']
            
            self.o1 = OptionMenu(master, self.var, "Remote Controller", "In-Band Controller", "OpenFlow Reference", "OVS Controller")
            self.o1.grid(row=rowCount, column=1, sticky=W)
            if controllerType == 'ref':
                self.var.set("OpenFlow Reference")
            elif controllerType == 'inband':
                self.var.set("In-Band Controller")
            elif controllerType == 'remote':
                self.var.set("Remote Controller")
            else:
                self.var.set("OVS Controller")
            rowCount+=1

            # Field for Remove Controller IP
            remoteFrame= LabelFrame(master, text='Remote/In-Band Controller', padx=5, pady=5)
            remoteFrame.grid(row=rowCount, column=0, columnspan=2, sticky=W)

            Label(remoteFrame, text="IP Address:").grid(row=0, sticky=E)
            
            self.e1 = Entry(remoteFrame)
            self.e1.grid(row=0, column=1)
            self.e1.insert(0, self.ctrlrValues['remoteIP'])
            rowCount+=1

            return self.hostnameEntry # initial focus

        def apply(self):
            hostname = self.hostnameEntry.get()
            controllerType = self.var.get()
            remoteIP = self.e1.get()
            controllerPort = int(self.e2.get())
            self.result = { 'hostname': hostname,
                            'remoteIP': remoteIP,
                            'remotePort': controllerPort}

            if controllerType == 'Remote Controller':
                self.result['controllerType'] = 'remote'
            elif controllerType == 'In-Band Controller':
                self.result['controllerType'] = 'inband'
            elif controllerType == 'OpenFlow Reference':
                self.result['controllerType'] = 'ref'
            else:
                self.result['controllerType'] = 'ovsc'

# Representation feature
class ToolTip(object):

    def __init__(self, widget):
        self.widget = widget
        self.tipwindow = None
        self.id = None
        self.x = self.y = 0

    def showtip(self, text):
        """Display text in tooltip window"""
        
        self.text = text
        if self.tipwindow or not self.text:
            return
        x, y, cx, cy = self.widget.bbox("insert")
        x = x + self.widget.winfo_rootx() + 27
        y = y + cy + self.widget.winfo_rooty() +27
        self.tipwindow = tw = Toplevel(self.widget)
        tw.wm_overrideredirect(1)
        tw.wm_geometry("+%d+%d" % (x, y))
        try:
            # For Mac OS
            
            tw.tk.call("::tk::unsupported::MacWindowStyle",
                       "style", tw._w,
                       "help", "noActivates")
        except TclError:
            pass
        label = Label(tw, text=self.text, justify=LEFT,
                      background="#ffffe0", relief=SOLID, borderwidth=1,
                      font=("tahoma", "8", "normal"))
        label.pack(ipadx=1)

    def hidetip(self):
        tw = self.tipwindow
        self.tipwindow = None
        if tw:
            tw.destroy()

# Main class - initialization, etc.
class MiniEdit( Frame, Utils.LoggerHelper ):

    """A simple network editor for Mininet."""

    def __init__( self, worker, parent=None, cheight=600, cwidth=800 ):
        sys.excepthook = self.fatal_error_handler
        Frame.__init__(self)
        self._root().report_callback_exception = self.gui_error_handler
        worker.error_handler = self.gui_error_handler

        self.TYPE_DUMMY = -1
        self.TYPE_ENDPOINT = "SAP"
        self.TYPE_FUNCTION = "VNF"
        self.TYPE_HOST = "HOST"
        self.TYPE_SWITCH = "SW"
        self.TYPE_CONTROLLER = "C"

        self.color_index = 0

        self.defaultIpBase='10.0.0.0/8'

        self.nflowDefaults = {'nflowTarget':'',
                              'nflowTimeout':'600',
                              'nflowAddId':'0'}
        self.sflowDefaults = {'sflowTarget':'',
                              'sflowSampling':'400',
                              'sflowHeader':'128',
                              'sflowPolling':'30'}

        self.appPrefs={
            "ipBase": self.defaultIpBase,
            "startCLI": "0",
            "terminalType": 'xterm',
            "switchType": 'ovs',
            "dpctl": '',
            'sflow':self.sflowDefaults,
            'netflow':self.nflowDefaults,
            'openFlowVersions':{'ovsOf10':'1',
                                'ovsOf11':'0',
                                'ovsOf12':'0',
                                'ovsOf13':'0'}

        }

        self._next_node_id = 0
        self.worker = worker

        # Init main modules - START
        
        # Init NodeManager
        self.node_manager = NodeManagerMininetWrapper()
        # Init VNFManager
        vnf_manager = Orchestrator.VNFManager()
        vnf_manager.set_node_manager(self.node_manager)
        # Init RouteManager
        self.rm = Orchestrator.RouteManager(vnf_manager)
        # Init NetworkManager
        self.network_manager = NetworkManagerMininet()

        self.network_manager.register_listener(self.rm)
        self.network_manager.register_listener(self)
        self.network_manager.vnf_manager = vnf_manager
        self.rm.register_listener(self)

        # Init network function and physical graphs
        self.nf_g = networkx.DiGraph()
        self.phy_g = networkx.Graph()
        # Init Orchestrator
        self.orchestrator = Orchestrator.Orchestrator(self.network_manager,
                                                      self.rm)

        # Init main modules - STOP
        
        self._gui_event_queue = Queue.Queue()

        self.vnf_proc_cmd = 'grep cpu /proc/stat'
        self.vnf_mcmd = 'grep MemTotal /proc/meminfo'

        self.control_buttons = dict()

        # Call superclass constructor
        Frame.__init__( self, parent )
        self.action = None
        self.appName = 'ESCAPE Dashboard'
        self.fixedFont = tkFont.Font ( family="DejaVu Sans Mono", size="14" )

        # Style
        self.font = ( 'Geneva', 9 )
        self.smallFont = ( 'Geneva', 7 )
        self.bg = 'white'

        # Title
        self.top = self.winfo_toplevel()
        self.top.title( self.appName )

        # Menu bar
        self.createMenubar()

        # Editing canvas
        self.cheight, self.cwidth = cheight, cwidth
        self.pwindow = PanedWindow( self, width=cwidth-30, height=cheight )

        self.nf_frame, self.nf_canvas = self.addPane( "Service graph" )
        self.phy_frame, self.phy_canvas = self.addPane( "Physical network" )
        self.nf_canvas.unifyType = 'NF'
        self.nf_canvas.itemToWidget = {}
        self.nf_canvas.idToWidget = {}
        self.nf_canvas.nameToWidget = {} #remove if nodes indexed with ids
        self.nf_canvas.links = {}
        self.nf_canvas.widgetToItem = {}
        self.nf_canvas.available = {'Vnf', 'Start', 'End', 'Startpoint'}
        self.nf_canvas.hostCount = 0
        self.nf_canvas.switchCount = 0
        self.nf_canvas.controllerCount = 0
        self.nf_canvas.links = {}
        self.nf_canvas.hostOpts = {}
        self.nf_canvas.switchOpts = {}
        self.nf_canvas.controllers = {}
        self.nf_canvas.vnfOpts = {}
        self.nf_canvas.startpointOpts = {}
        self.nf_canvas.vnfCount = 0
        self.nf_canvas.startpointCount = 0


        self.phy_canvas.unifyType = 'PHY'
        self.phy_canvas.available = {'Switch', 'Host', 'Startpoint', 'Controller'}
        self.phy_canvas.itemToWidget = {}
        self.phy_canvas.widgetToItem = {}
        self.phy_canvas.idToWidget = {}
        self.phy_canvas.nameToWidget = {} #remove if nodes indexed with ids
        self.phy_canvas.links = {}
        self.phy_canvas.hostCount = 0
        self.phy_canvas.switchCount = 0
        self.phy_canvas.controllerCount = 0
        self.phy_canvas.links = {}
        self.phy_canvas.hostOpts = {}
        self.phy_canvas.switchOpts = {}
        self.phy_canvas.controllers = {}
        self.phy_canvas.vnfOpts = {}
        self.phy_canvas.startpointOpts = {}
        self.phy_canvas.vnfCount = 0
        self.phy_canvas.startpointCount = 0

        # Toolbar
        self.images = miniEditImages()
        self.buttons = {}
        self.active = None
        self.tools = ( 'Select', 'Switch', 'Controller', 'NetLink', 'Host', 'Startpoint' )
        self.networkfunctions = {'Vnf'}
        self.customColors = { 'Switch': 'darkGreen', 'Host': 'blue' }
        self.toolbar = self.createToolbar()

        # Layout
        self.toolbar.grid( column=0, row=0, sticky='nsew')
        self.pwindow.grid( column=1, row=0, sticky='nsew' )
        self.columnconfigure( 1, weight=1 )
        self.rowconfigure(0, weight = 1)

        self.log_window = LogWindow(self)
        self.log_window.place(relx = 1, rely = 1,
                              x = -14, y = -16,
                              relwidth = 0.4, relheight = 0.3,
                              anchor = tk.SE)

        wl = WidgetLogger(scheduler = self.schedule,
                          printer = self.log_window.log,
                          formatter = self.gui_log_formatter)
        logging.getLogger().addHandler(wl)

        self.pack( expand=True, fill='both' )
        # About box
        self.aboutBox = None

        # Initialize node data
        self.nodeBindings = self.createNodeBindings()
        self.nodePrefixes = { 'LegacyRouter': 'r', 'LegacySwitch': 's', 'Switch': 's', 'Host': 'h' , 'Controller': 'c', 'Vnf': 'lb', 'Startpoint': 'sap'}

        # Initialize link tool
        self.link = self.linkWidget = None

        # Selection support
        self.selection = None
        self.actualCanvas = None

        # Keyboard bindings
        self.bind( '<Control-q>', lambda event: self.quit() )
        self.bind( '<KeyPress-Delete>', self.deleteSelection )
        self.bind( '<KeyPress-BackSpace>', self.deleteSelection )
        self.focus()

        
        def add_menu(name, label, properties=True):
            """self.namePopup = Menu(),
            Properties menu entry will call self.nameDetails"""
            m = Menu(self.top, tearoff=0)
            m.name = name
            setattr(self, name + 'Popup', m)
            m.add_command(label=label, font=self.font, state=DISABLED,
                          background='black', foreground='white')
            #m.add_separator()
            if properties:
                # add 'properties' menu item
                d = getattr(self, name + 'Details')
                c = lambda: d(getattr(self, name+'Popup').canvas)
                m.add_command(label='Properties', font=self.font, command=c)
            return m

        def add_command(menu, label, cmd):
            name = menu.name + 'Popup'
            c = lambda: cmd(getattr(self, name).canvas)
            menu.add_command(label=label, font=self.font, command=c)

        add_menu('host', 'Container Options')

        add_menu('vnf', 'VNF Options')

        m = add_menu('vnfRun', 'VNF Options', False)
        # runnin Terminal on VNF is disabled
        # add_command(m, 'Terminal', self.xterm)
        add_command(m, 'Start clicky', self.start_clicky)

        add_menu('startpoint', 'SAP Options')

        m = add_menu('startpointRun', 'SAP Options', False)
        add_command(m, 'Terminal', self.xterm)
        #add_command(m, 'Start clicky', self.start_clicky)

        m = add_menu('hostRun', 'Container Options', False)
        add_command(m, 'Terminal',  self.xterm)
        add_command(m, 'Start clicky', self.start_clicky)

        m = add_menu('legacyRouterRun', 'Router Options', False)
        add_command(m, 'Terminal', self.xterm)

        add_menu('switch', 'Switch Options')

        m = add_menu('switchRun', 'Switch Options', False)
        add_command(m, 'Properties', self.switchDetails)

        add_menu('link', 'Link Options')

        m = add_menu('linkRun', 'Link Options', False)
        add_command(m, 'Link Up', self.linkUp)
        add_command(m, 'Link Down', self.linkDown)

        add_menu('controller', 'Controller Options')

        # Event handling initalization
        self.linkx = self.linky = self.linkItem = None
        self.lastSelection = None

        self.net = None

        # Close window gracefully
        Wm.wm_protocol( self.top, name='WM_DELETE_WINDOW', func=self.quit )

        self._update()

    def _update(self):
		# Get 10 event from GUI queue and invoke referred functions
        
        for i in xrange(10):
            try:
                (f, args, kw) = self._gui_event_queue.get(False)
            except Queue.Empty:
                break
            self.after_idle(f, *args, **kw)

        self.after(20, self._update)

    def schedule(self, function, *args, **kw):
		# Put functions in queue
        self._gui_event_queue.put((function, args, kw), block = False)

    
    def gui_log_formatter(self, logrecord):
        msg = r'[l]%s[|l]([f]%s[|f]): [t]%s[|t]'%(logrecord.levelname,
                                                  logrecord.module,
                                                  logrecord.message)
        msg += '\n'
        return msg

    def log_to_widget(self, msg):
        pass

    def next_id(self):
        _id = self._next_node_id
        self._next_node_id += 1
        return _id

    def quit( self ):
        """Stop our network, if any, then quit."""
        self.stop_network()
        Frame.quit( self )

    def createMenubar( self ):
        """Create our menu bar."""

        font = self.font

        
        self.mbar = mbar = Menu( self.top, font=font )
        self.top.configure( menu=mbar )


        
        self.fileMenu = fileMenu = Menu( mbar, tearoff=False )
        mbar.add_cascade( label="File", font=font, menu=fileMenu )
        fileMenu.add_command( label="New", font=font, command=self.newTopologies )
        fileMenu.add_command( label="Open NF chain", font=font, command=self.loadNFTopology )
        fileMenu.add_command( label="Open PHY topo", font=font, command=self.loadPHYTopology )
        fileMenu.add_command( label="Save NF chain", font=font, command=self.saveNFTopology )
        fileMenu.add_command( label="Save PHY topo", font=font, command=self.savePHYTopology )
        fileMenu.add_separator()
        fileMenu.add_command( label='Quit', command=self.quit, font=font )

        
        self.editMenu = editMenu = Menu( mbar, tearoff=False )
        mbar.add_cascade( label="Edit", font=font, menu=editMenu )
        editMenu.add_command( label="Preferences", font=font, command=self.prefDetails)

        
        self.runMenu = runMenu = Menu( mbar, tearoff=False )
        mbar.add_cascade( label="Run", font=font, menu=runMenu )
        runMenu.add_command( label="Run", font=font, command=self.doRun )
        runMenu.add_command( label="Stop", font=font, command=self.doStop )
        fileMenu.add_separator()
        runMenu.add_command( label='Show OVS Summary', font=font, command=self.ovsShow )
        runMenu.add_command( label='Root Terminal', font=font, command=self.rootTerminal )
        runMenu.add_command( label='Start CLI', font=font, command=self.startCLI )

    # Canvas

    def addPane( self, name = None):
        """Create and return our scrolling canvas frame."""
        f = Frame( self.pwindow )
        canvas = Canvas( f, bg=self.bg )
        canvas.disabled = False

        # Scroll bars
        xbar = Scrollbar( f, orient='horizontal', command=canvas.xview )
        ybar = Scrollbar( f, orient='vertical', command=canvas.yview )
        canvas.configure( xscrollcommand=xbar.set, yscrollcommand=ybar.set )

        # Resize box
        resize = Label( f, bg='white' )

        # Layout
        canvas.grid( row=0, column=1, sticky='nsew')
        ybar.grid( row=0, column=2, sticky='ns')
        xbar.grid( row=1, column=1, sticky='ew' )
        resize.grid( row=1, column=2, sticky='nsew' )

        # Resize behavior
        f.rowconfigure( 0, weight=1 )
        f.columnconfigure( 1, weight=1 )
        f.grid( row=0, column=0, sticky='nsew' )
        f.bind( '<Configure>', lambda event: self.updateScrollRegion(canvas) )

        # Mouse bindings
        canvas.bind( '<ButtonPress-1>', self.clickCanvas )
        canvas.bind( '<B1-Motion>', self.dragCanvas )
        canvas.bind( '<ButtonRelease-1>', self.releaseCanvas )

        if name:
            canvas.name = Label(f, text = name)
            canvas.name.place(relx = 0, rely = 0, anchor = tk.NW)

        self.pwindow.add( f, stretch='always' )
        return f, canvas

    
    def updateScrollRegion( self, canvas ):
        """Update canvas scroll region to hold everything."""
        bbox = canvas.bbox( 'all' )
        if bbox is not None:
            canvas.configure( scrollregion=( 0, 0, bbox[ 2 ],
                                   bbox[ 3 ] ) )

    
    def canvasx( self, x_root, canvas ):
        """Convert root x coordinate to canvas coordinate."""
        return canvas.canvasx( x_root ) - canvas.winfo_rootx()

    
    def canvasy( self, y_root, canvas ):
        """Convert root y coordinate to canvas coordinate."""
        return canvas.canvasy( y_root ) - canvas.winfo_rooty()

    # Toolbar

    def activate( self, toolName ):
        """Activate a tool and press its button."""
        # Adjust button appearance
        if self.active:
            self.buttons[ self.active ].configure( relief='raised' )
        self.buttons[ toolName ].configure( relief='sunken' )
        # Activate dynamic bindings
        self.active = toolName


    
    def createToolTip(self, widget, text):
        toolTip = ToolTip(widget)
        
        def enter(event):
            toolTip.showtip(text)

        
        def leave(event):
            toolTip.hidetip()
        widget.bind('<Enter>', enter)
        widget.bind('<Leave>', leave)

    def createToolbar( self ):
        """Create and return our toolbar frame."""

        toolbar = Frame( self )

        tooltips = { 'Host': 'VNF container',
                     'Startpoint': 'Service Attachment Point',
                     }

        # Tools
        for tool in self.tools:
            cmd = ( lambda t=tool: self.activate( t ) )
            b = Button( toolbar, text=tool, font=self.smallFont, command=cmd)
            if tool in self.images:
                b.config( height=35, image=self.images[ tool ] )
                self.createToolTip(b, tooltips.get(str(tool), str(tool)))
                # b.config( compound='top' )
            b.pack( fill='x' )
            self.buttons[ tool ] = b
        self.activate( self.tools[ 0 ] )

        separator = Frame(toolbar, height=2, bd=1, relief=tk.SUNKEN)
        separator.pack(fill=tk.X, padx=15, pady=15)

        # network functions
        for tool in self.networkfunctions:
            cmd = ( lambda t=tool: self.activate( t ) )
            b = Button( toolbar, text=tool, font=self.smallFont, command=cmd)
            if tool in self.images:
                b.config( height=35, image=self.images[ tool ] )
                self.createToolTip(b, str(tool))
                # b.config( compound='top' )
            b.pack( fill='x' )
            self.buttons[ tool ] = b

        # Spacer
        Label( toolbar, text='' ).pack()

        # Commands
        for cmd, color, text in [
            ( 'Stop', 'darkRed', 'Stop network' ),
            ( 'Run', 'darkGreen', 'Start network' ),
            ( 'Orchestrate', 'darkBlue', 'Start services' ),
            ( 'StopChains', 'darkBlue', 'Stop services' )]:

            doCmd = getattr( self, 'schedule' + cmd )
            b = Button( toolbar, text=text, font=self.smallFont,
                        width = 10, fg=color, command=doCmd, state = tk.DISABLED )
            self.control_buttons[cmd] = b
            b.pack( fill='x', side='bottom' )
        self.change_button_status(NetworkManagerMininet.DOWN)

        return toolbar

    def scheduleOrchestrate(self):
        self.worker.schedule(self.doOrchestrate)

    def scheduleStopChains(self):
        self.worker.schedule(self.doStopChains)

    def scheduleRun(self):
        self.worker.schedule(self.doRun)

    def scheduleStop(self):
        self.worker.schedule(self.doStop)

	# Start Service Graph operation
    
    def doOrchestrate(self):
		# Invoke the orchestration steps
        self.disable_canvas(self.nf_canvas)
        self.set_chain_related_menu(tk.DISABLED)
        self.disable_toolbar()
        self.control_buttons['Orchestrate'].config(state = tk.DISABLED)
        try:
            # Start orchestration method - return the newly created VNFs
            # dump(self.phy_g, 'MiniEdit phy_g topo')
            #vnf_to_host_list = self.orchestrator.start(self.nf_g)
            vnf_to_host_list = self.orchestrator.start(self.nf_g, self.phy_g)
        except RuntimeError as e:
            #TODO: What if rollback needed?(e.g: last route hop install failed?)
            self._gui_warn('Orchestration failed\n%s'%e)
            self.enable_canvas(self.nf_canvas)
            self.enable_toolbar()
            self.control_buttons['Orchestrate'].config(state = tk.NORMAL)
            return

        # self.draw_vnfs_in_res_panel(vnf_to_host_list)

        # draw only static VNFs at start
        for vnf, host in vnf_to_host_list:
            ee_type = self.phy_g.node[host].get('ee_type')
            if ee_type in ['static']:
                self.draw_vnf_in_res_panel(vnf, host)

        self.control_buttons['StopChains'].config(state = tk.NORMAL)

    def draw_vnfs_in_res_panel(self, vnf_to_host_list):
        distance = 60
        for vnf, host in vnf_to_host_list:
            host_id = self.phy_g.node[host]['_id'] #later host var will contain the _id
            vnf_id = self.nf_g.node[vnf]['_id']
            
            orig_vnf = self.nf_canvas.idToWidget[vnf_id]
            widget = self.phy_canvas.idToWidget[host_id]
            host_canvas_id = self.phy_canvas.widgetToItem[widget]
            neighbour = len(widget.links)
            nx, ny = self.phy_canvas.coords(host_canvas_id)

            x = nx + math.sin(neighbour)*200
            y = ny + math.cos(neighbour)*200
            ops = {'_id': self.next_id(),
                   'node_type': self.TYPE_FUNCTION
                   }
            node = 'Vnf'
            name = vnf
            canvas = self.phy_canvas
            orig_opts = self.nf_canvas.vnfOpts[name]
            ee_type = self.phy_g.node[host].get('ee_type')
            if ee_type in ['netconf', 'remote']:
                n_tags = node
                l_tags = 'link'
            else:
                n_tags = (node, 'del_if_stopped')
                l_tags = ('link', 'del_if_stopped')
            icon = self.nodeIcon( node, name, canvas, orig_opts )
            icon.cloned = orig_vnf
            item = canvas.create_window( x, y, anchor=tk.CENTER, window=icon,
                                         tags=n_tags )
            canvas.widgetToItem[ icon ] = item
            canvas.itemToWidget[ item ] = icon
            canvas.nameToWidget[ name ] = icon
            icon.links = {}
            icon.parent_vnf = host
            orig_vnf.parent_vnf = host

            icon.bind('<Button-3>', self.do_vnfPopup )

            self.link = canvas.create_line( nx, ny, x, y, width=4,
                                            dash=(3, 3),
                                            fill='ForestGreen', tag=l_tags )
            widget.links[ icon ] = self.link
            icon.links[ widget ] = self.link
            canvas.links[ self.link ] = {'type' :'data',
                                       'src':widget,
                                       'dest':icon}
            # change state of VNF mapped to static node to 'running'
            if ee_type in ['static']:
                self.change_node_status(icon, 'running')

            self.link = None

    def draw_vnf_in_res_panel(self, vnf, host):
        # Draw a single VNF connecting to HOST
        distance = 60
        host_id = self.phy_g.node[host]['_id'] #later host var will contain the _id
        self._debug('vnf: %s  NF_G.nodes: %s' % (vnf, self.nf_g.nodes()))
        vnf_id = self.nf_g.node[vnf]['_id']
        orig_vnf = self.nf_canvas.idToWidget[vnf_id]
        widget = self.phy_canvas.idToWidget[host_id]
        host_canvas_id = self.phy_canvas.widgetToItem[widget]
        neighbour = len(widget.links)
        nx, ny = self.phy_canvas.coords(host_canvas_id)

        x = nx + math.sin(neighbour)*200
        y = ny + math.cos(neighbour)*200
        ops = {'_id': self.next_id(),
               'node_type': self.TYPE_FUNCTION
               }
        node = 'Vnf'
        name = vnf
        canvas = self.phy_canvas
        orig_opts = self.nf_canvas.vnfOpts[name]
        ee_type = self.phy_g.node[host].get('ee_type')
        if ee_type in ['netconf', 'remote']:
            n_tags = (node)
            l_tags = ('link')
        else:
            n_tags = (node, 'del_if_stopped')
            l_tags = ('link', 'del_if_stopped')

        icon = self.nodeIcon( node, name, canvas, orig_opts )
        icon.cloned = orig_vnf
        item = canvas.create_window( x, y, anchor=tk.CENTER, window=icon,
                                     tags=n_tags )
        canvas.widgetToItem[ icon ] = item
        canvas.itemToWidget[ item ] = icon
        canvas.nameToWidget[ name ] = icon
        icon.links = {}
        icon.parent_vnf = host
        orig_vnf.parent_vnf = host

        icon.bind('<Button-3>', self.do_vnfPopup )

        self.link = canvas.create_line( nx, ny, x, y, width=4,
                                        dash=(3, 3),
                                        fill='ForestGreen', tag=l_tags )
        widget.links[ icon ] = self.link
        icon.links[ widget ] = self.link
        canvas.links[ self.link ] = {'type' :'data',
                                     'src':widget,
                                     'dest':icon}
        # change state of VNF mapped to static node to 'running'
        if ee_type in ['static']:
            self.change_node_status(icon, 'running')
            
        self.link = None

    def change_node_status(self, widget, new_status, keep=None):
        """
        Change node's status to 'new_status',
        unless the current status is 'keep'
        """
        try:
            if widget.status == keep:
                return
        except AttributeError:
            pass
        status_to_color = {'running': 'green',
                           'stopped': 'red',
                           'starting': 'yellow',
                           'failed': 'orangered',
                           }
        color = status_to_color.get(new_status, 'gray')
        widget.status = new_status
        widget.config(highlightbackground=color, highlightthickness=3)

    def _handle_route_state_change(self, event):
        self._debug('%d route status changed to %s'%(event.id, event.status))
        self.worker.schedule(self.update_link_by_route_state, event)

    def _handle_network_state_change(self, event):
        self.change_button_status(event.state)
        # force 'stopped' state for all nodes if NetworkManager.DOWN
        from NetworkManager import NetworkManagerMininet as nmm
        if event.state == nmm.DOWN:
            for w in self.phy_canvas.nameToWidget.values():
                if w:
                    self.change_node_status(w, 'stopped')

    def change_button_status(self, state):
        from NetworkManager import NetworkManagerMininet as nmm
        config = {'Orchestrate': {nmm.SCANNED:  {'state': tk.NORMAL},
                                  nmm.UP:       {'state': tk.NORMAL},
                                  nmm.DOWN:     {'state': tk.DISABLED},
                                  nmm.STARTING: {'state': tk.DISABLED},
                                  nmm.STOPPING: {'state': tk.DISABLED},
                                  },
                  'StopChains': {nmm.SCANNED:  {'state': tk.DISABLED},
                                 nmm.UP:       {'state': tk.DISABLED},
                                 nmm.DOWN:     {'state': tk.DISABLED},
                                 nmm.STARTING: {'state': tk.DISABLED},
                                 nmm.STOPPING: {'state': tk.DISABLED},
                                 },
                  'Stop': {nmm.SCANNED: {'state': tk.NORMAL},
                           nmm.UP:      {'state': tk.NORMAL},
                           nmm.DOWN:    {'state': tk.DISABLED},
                           nmm.STARTING:{'state': tk.DISABLED},
                           nmm.STOPPING: {'state': tk.DISABLED},
                           },
                  'Run': {nmm.SCANNED:  {'state': tk.DISABLED},
                          nmm.UP:       {'state': tk.DISABLED},
                          nmm.DOWN:     {'state': tk.NORMAL},
                          nmm.STARTING: {'state': tk.DISABLED},
                          nmm.STOPPING: {'state': tk.DISABLED},
                          }
                  }
        for button, c in config.iteritems():
            self.control_buttons[button].config(c[state])

    def _handle_switch_connection_up(self, event):
        w = self.phy_canvas.nameToWidget.get(event.name)
        if not w:
            return
        self.change_node_status(w, 'running')

    def _handle_switch_connection_down(self, event):
        w = self.phy_canvas.nameToWidget.get(event.name)
        if not w:
            return
        self.change_node_status(w, 'stopped')

    def _handle_vnf_update(self, event):
        w = self.phy_canvas.nameToWidget.get(event.name)
        # self._debug('PHY_G before VNF_UPDATE: %s' % self.phy_g.nodes())
        # self._debug('W: %s' % w)
        # if not w:
        #     return
        if not w:
            self.draw_vnf_in_res_panel(event.name, event.on_node)
            w = self.phy_canvas.nameToWidget.get(event.name)
        self.updateGraphEdge(event.name, w.parent_vnf, {}, self.phy_canvas)
        self.phy_g.node[event.name]['node_type'] = self.TYPE_FUNCTION
        self.change_node_status(w, event.status)
        if event.status == 'stopped':
            try:
                w = self.phy_canvas.nameToWidget[ event.name ]
                i = self.phy_canvas.widgetToItem[ w ]
                self.remove_one_vnf_from_res_panel(i)
                del self.phy_canvas.nameToWidget[ event.name ]
            except KeyError:
                pass
            self.phy_g.remove_node( event.name )
        # self._debug('PHY_G after VNF_UPDATE: %s' % self.phy_g.nodes())
        self.rm.install_pending_routes(self.phy_g)

    
    def find_link_by_ends(self, i, j, canvas):
        try:
            w_i = canvas.nameToWidget[i]
            w_j = canvas.nameToWidget[j]
        except KeyError:
            # link has already deleted due to node delete
            return None
        for link in w_i.links.values():
            c_link = canvas.links[link]
            if c_link['dest'] == w_j or c_link['src'] == w_j:
                return link
        return None

    
    def update_link_by_route_state(self, event):
        config = {}
        colors = {traffic_steering.RouteChanged.FAILED: 'red',
                  traffic_steering.RouteChanged.PENDING: 'yellow',
                  traffic_steering.RouteChanged.STARTING: 'lightblue',
                  traffic_steering.RouteChanged.STARTED: 'green',
                  traffic_steering.RouteChanged.REMOVING: 'tomato',
                  traffic_steering.RouteChanged.REMOVED: 'blue',
                  }
        config = {'fill': colors.get(event.status, 'pink')}

        route_id = event.id
        route_tag = 'route'+str(route_id)

        
        map = ( (event.route_map['chain'], self.nf_canvas),
                (event.route_map['res'], self.phy_canvas) )

        for route_map, canvas in map:
            for i,j in route_map:
                #self._debug('update link between %s - %s with route tag %s'
                #            %(i,j, route_tag))
                link = self.find_link_by_ends(i, j, canvas)
                if link:
                    canvas.itemconfig(link, **config)
                    canvas.addtag_withtag(route_tag, link)

    def disable_toolbar(self):
        self.activate( 'Select' ) #always(?) activate select button
        for tool in self.tools:
            self.buttons[ tool ].config( state='disabled' )
        for nf in self.networkfunctions:
            self.buttons[ nf ].config( state='disabled' )

    def init_nodes_status(self):
        for name, icon in self.phy_canvas.nameToWidget.iteritems():
            node = self.phy_g.node.get(name, {})
            if node.get('node_type') == self.TYPE_CONTROLLER:
                # pox is always running
                self.change_node_status(icon, 'running')
            else:
                self.change_node_status(icon, 'starting', keep='running')

    def set_nodes_status(self):
        for name, icon in self.phy_canvas.nameToWidget.iteritems():
            node = self.phy_g.node.get(name, {})
            
            type = node.get('node_type')
            ee_type = node.get('ee_type')
            if type == self.TYPE_HOST and ee_type not in ['netconf', 'remote']:
                self.change_node_status(icon, 'running')
            elif type == self.TYPE_ENDPOINT:
                self.change_node_status(icon, 'running')

    
    def enable_canvas(self, canvas):
        canvas.disabled = False

    
    def disable_canvas(self, canvas):
        canvas.disabled = True

    def set_network_related_menu(self, state):
        self.fileMenu.entryconfig(0, state = state)
        self.fileMenu.entryconfig(2, state = state)
        self.editMenu.entryconfig(0, state = state)
        self.runMenu.entryconfig(0, state = state)

    def set_chain_related_menu(self, state):
        self.fileMenu.entryconfig(1, state = state)
	
    # Start Physical Topology operation
    def doRun( self ):
        """Run command."""
        self.control_buttons['Run'].config(state = tk.DISABLED)
        self.activate( 'Select' )
        self.disable_canvas(self.phy_canvas)
        self.init_nodes_status()
        self.set_network_related_menu(tk.DISABLED)

        # Start physical network according to physical graph
        self.start_network(self.phy_g, self.appPrefs)
        # Reset RouteManager
        self.rm.reset()

        for icon in self.phy_canvas.widgetToItem:
            icon.config(bg = '#BDCDBD')

        self.set_nodes_status()

    def remove_vnf_from_res_panel(self):
        for item in self.phy_canvas.find_withtag('del_if_stopped'):
            self.remove_one_vnf_from_res_panel(item)

    def remove_one_vnf_from_res_panel(self, item):
        if item not in self.phy_canvas.itemToWidget:
            return
        w = self.phy_canvas.itemToWidget[item]
        del w.cloned.parent_vnf
        for link in w.links.values():
            pair = self.phy_canvas.links.get( link, None )
            if pair is not None:
                source=pair['src']
                dest=pair['dest']
                del source.links[ dest ]
                del dest.links[ source ]
            del self.phy_canvas.links[link]
            self.phy_canvas.delete(link)
        del self.phy_canvas.widgetToItem[ w ]
        del self.phy_canvas.itemToWidget[ item ]
        self.phy_canvas.delete(item)

    def enable_toolbar(self):
        for tool in self.tools:
            self.buttons[ tool ].config( state='normal' )
        for nf in self.networkfunctions:
            self.buttons[ nf ].config( state='normal' )

    def reset_links_color(self):
        self.nf_canvas.itemconfig('link', fill = 'blue')

    def reset_nodes_status(self):
        for name, icon in self.phy_canvas.nameToWidget.iteritems():
            node = self.phy_g.node.get(name, {})
            
            type = node.get('node_type')
            ee_type = node.get('ee_type')
            
            if type == self.TYPE_HOST and ee_type not in ['netconf', 'remote']:
                self.change_node_status(icon, 'stopped')
            elif type == self.TYPE_ENDPOINT:
                self.change_node_status(icon, 'stopped')

	# Stop Service Graph operation

    def doStopChains(self):
        self.control_buttons['StopChains'].config(state = tk.DISABLED)
        # Stop service graph
        self.orchestrator.stop_service_graphs()
		
        self.remove_vnf_from_res_panel()
        self.control_buttons['Orchestrate'].config(state = tk.NORMAL)
        self.enable_toolbar()
        self.enable_canvas(self.nf_canvas)
        self.set_chain_related_menu(tk.NORMAL)

	# Stop Physical Topology operation
    def doStop( self ):
        """Stop command."""
        # Stop the service chain prior
        self.doStopChains()

        self.enable_canvas(self.phy_canvas)
        # Stop the physical topology
        self.stop_network()

        self.reset_links_color()
        for icon in self.phy_canvas.widgetToItem:
            icon.config(bg = '#D9D9D9')

        self.reset_nodes_status()
        self.set_network_related_menu(tk.NORMAL)


    def addNode( self, node, nodeNum, x, y, canvas, name=None):
        """Add a new node to our canvas."""
        options = dict()
        options['node_type']=self.TYPE_DUMMY
        if name is None:
            name = self.nodePrefixes[ node ] + nodeNum
        if 'Switch' == node:
            canvas.switchCount += 1
            options = canvas.switchOpts[name]
            options['node_type'] = self.TYPE_SWITCH
        if 'Host' == node:
            canvas.hostCount += 1
            options = canvas.hostOpts[name]
            options['node_type'] = self.TYPE_HOST
        if 'Controller' == node:
            canvas.controllerCount += 1
            options = canvas.controllers[name]
            options['node_type'] = self.TYPE_CONTROLLER
        if 'Vnf' == node:
            canvas.vnfCount += 1
            options = canvas.vnfOpts[name]
            options['node_type'] = self.TYPE_FUNCTION
        if 'Startpoint' == node:
            canvas.startpointCount += 1
            options = canvas.startpointOpts[name]
            options['node_type'] = self.TYPE_ENDPOINT

        widget, canvas_id = self.addNamedNode(node, name, x, y, canvas, options)
        self.updateGraphNode(name, options, canvas, canvas_id)


    def addNamedNode( self, node, name, x, y, canvas, options):
        """Add a new node to our canvas."""
        icon = self.nodeIcon( node, name, canvas, options )
        item = canvas.create_window( x, y, anchor=tk.CENTER, window=icon,
                                     tags=node )
        canvas.widgetToItem[ icon ] = item
        canvas.itemToWidget[ item ] = icon
        canvas.idToWidget[ options['_id'] ] = icon
        canvas.nameToWidget[name] = icon
        icon.links = {}
        return icon, item

    
    def loadNFTopology( self, file = None ):
        try:
            self.loadTopology(self.nf_canvas, file)
        except IOError as e:
            self._gui_warn('Can not load %s service graph topology\n%s'%(file, e))
        except Exception as e:
            #TODO: get file name, if we used tkFileDialog
            self._gui_warn('Can not load given topology\n%s'%e)

    def loadPHYTopology( self, phy_file = None ):
        try:
            self.loadTopology(self.phy_canvas, phy_file)
        except IOError as e:
            self._gui_warn('Can not load %s physical topology\n%s'%(phy_file, e))
        except Exception as e:
            #TODO: get file name, if we used tkFileDialog
            self._gui_warn('Can not load given topology\n%s'%e)

    def loadTopology( self, canvas, topo_file = None ):
        """Load command."""

        myFormats = [
            ('Mininet Topology','*.mn'),
            ('All Files','*'),
        ]
        if topo_file is None:
            f = tkFileDialog.askopenfile(filetypes=myFormats, mode='rb')
        else:
            f = open(topo_file, 'rb')

        if f is None:
            return

        self.newTopology(canvas)
        loadedTopology = eval(f.read())

        # Load application preferences
        if 'application' in loadedTopology:
            self.appPrefs = dict(self.appPrefs.items() + loadedTopology['application'].items())
            if "ovsOf10" not in self.appPrefs["openFlowVersions"]:
                self.appPrefs["openFlowVersions"]["ovsOf10"] = '0'
            if "ovsOf11" not in self.appPrefs["openFlowVersions"]:
                self.appPrefs["openFlowVersions"]["ovsOf11"] = '0'
            if "ovsOf12" not in self.appPrefs["openFlowVersions"]:
                self.appPrefs["openFlowVersions"]["ovsOf12"] = '0'
            if "ovsOf13" not in self.appPrefs["openFlowVersions"]:
                self.appPrefs["openFlowVersions"]["ovsOf13"] = '0'
            if "sflow" not in self.appPrefs:
                self.appPrefs["sflow"] = self.sflowDefaults
            if "netflow" not in self.appPrefs:
                self.appPrefs["netflow"] = self.nflowDefaults

        # Load controllers
        if 'controllers' in loadedTopology:
            if loadedTopology['version'] == '1':
                # This is old location of controller info
                hostname = 'c0'
                canvas.controllers = dict()
                canvas.controllers[hostname] = loadedTopology['controllers']['c0']
                canvas.controllers[hostname]['hostname'] = hostname
                self.addNode('Controller', 0, float(30), float(30), name=hostname, canvas = canvas)
                icon = self.findWidgetByName(hostname, canvas)
                icon.bind('<Button-3>', self.do_controllerPopup )
            else:
                controllers = loadedTopology['controllers']
                for controller in controllers:
                    hostname = controller['opts']['hostname']
                    x = controller['x']
                    y = controller['y']
                    canvas.controllers[hostname] = controller['opts']
                    self.addNode('Controller', 0, float(x), float(y), name=hostname, canvas = canvas)
                    icon = self.findWidgetByName(hostname, canvas)
                    icon.bind('<Button-3>', self.do_controllerPopup )


        # Load hosts
        hosts = loadedTopology['hosts']
        for host in hosts:
            nodeNum = host['number']
            hostname = 'h'+nodeNum
            if 'hostname' in host['opts']:
                hostname = host['opts']['hostname']
            else:
                host['opts']['hostname'] = hostname
            if 'nodeNum' not in host['opts']:
                host['opts']['nodeNum'] = int(nodeNum)
            x = host['x']
            y = host['y']
            canvas.hostOpts[hostname] = host['opts']
            self.addNode('Host', nodeNum, float(x), float(y), name=hostname, canvas = canvas)
            icon = self.findWidgetByName(hostname, canvas)
            icon.bind('<Button-3>', self.do_hostPopup )

        # Load vnfs
        vnfs = loadedTopology['vnfs']
        for vnf in vnfs:
            nodeNum = vnf['number']
            name = self.nodePrefixes['Vnf']+nodeNum
            if 'name' in vnf['opts']:
                name = vnf['opts']['name']
            else:
                vnf['opts']['name'] = name
            if 'nodeNum' not in vnf['opts']:
                vnf['opts']['nodeNum'] = int(nodeNum)
            x = vnf['x']
            y = vnf['y']
            canvas.vnfOpts[name] = vnf['opts']
            self.addNode('Vnf', nodeNum, float(x), float(y), name=name, canvas = canvas)
            icon = self.findWidgetByName(name, canvas)
            icon.bind('<Button-3>', self.do_vnfPopup )

        #Load start/endpoint
        startpoints = loadedTopology['startpoints']
        for startpoint in startpoints:
            nodeNum = startpoint['number']
            startpointname = self.nodePrefixes['Startpoint']+nodeNum
            if 'name' in startpoint['opts']:
                startpointname = startpoint['opts']['name']
            else:
                startpoint['opts']['name'] = startpointname
            if 'nodeNum' not in startpoint['opts']:
                startpoint['opts']['nodeNum'] = int(nodeNum)
            x = startpoint['x']
            y = startpoint['y']
            canvas.startpointOpts[startpointname] = startpoint['opts']
            self.addNode('Startpoint', nodeNum, float(x), float(y), name=startpointname, canvas = canvas)
            icon = self.findWidgetByName(startpointname, canvas)
            icon.bind('<Button-3>', self.do_startpointPopup )

        # Load switches
        switches = loadedTopology['switches']
        for switch in switches:
            nodeNum = switch['number']
            hostname = 's'+nodeNum
            if 'controllers' not in switch['opts']:
                switch['opts']['controllers'] = []
            if 'switchType' not in switch['opts']:
                switch['opts']['switchType'] = 'default'
            if 'hostname' in switch['opts']:
                hostname = switch['opts']['hostname']
            else:
                switch['opts']['hostname'] = hostname
            if 'nodeNum' not in switch['opts']:
                switch['opts']['nodeNum'] = int(nodeNum)
            x = switch['x']
            y = switch['y']
            canvas.switchOpts[hostname] = switch['opts']
            if switch['opts']['switchType'] == "legacyRouter":
                self.addNode('LegacyRouter', nodeNum, float(x), float(y), name=hostname, canvas = canvas)
                icon = self.findWidgetByName(hostname, canvas)
                icon.bind('<Button-3>', self.do_legacyRouterPopup )
            elif switch['opts']['switchType'] == "legacySwitch":
                self.addNode('LegacySwitch', nodeNum, float(x), float(y), name=hostname, canvas = canvas)
                icon = self.findWidgetByName(hostname, canvas)
                icon.bind('<Button-3>', self.do_legacySwitchPopup )
            else:
                self.addNode('Switch', nodeNum, float(x), float(y), name=hostname, canvas = canvas)
                icon = self.findWidgetByName(hostname, canvas)
                icon.bind('<Button-3>', self.do_switchPopup )

            # create links to controllers
            if int(loadedTopology['version']) > 1:
                controllers = canvas.switchOpts[hostname]['controllers']
                for controller in controllers:
                    dest = self.findWidgetByName(controller, canvas)
                    dx, dy = canvas.coords( canvas.widgetToItem[ dest ] )
                    self.link = canvas.create_line(float(x),
                                                        float(y),
                                                        dx,
                                                        dy,
                                                        width=4,
                                                        fill='red',
                                                        dash=(6, 4, 2, 4),
                                                        tag='link' )
                    canvas.itemconfig(self.link, tags=canvas.gettags(self.link)+('control',))
                    self.addLink( icon, dest, canvas, linktype='control' )
                    self.createControlLinkBindings(canvas)
                    self.link = self.linkWidget = None
            else:
                dest = self.findWidgetByName('c0', canvas)
                dx, dy = canvas.coords( canvas.widgetToItem[ dest ] )
                self.link = canvas.create_line(float(x),
                                                    float(y),
                                                    dx,
                                                    dy,
                                                    width=4,
                                                    fill='red',
                                                    dash=(6, 4, 2, 4),
                                                    tag='link' )
                canvas.itemconfig(self.link, tags=canvas.gettags(self.link)+('control',))
                self.addLink( icon, dest, canvas, linktype='control' )
                self.createControlLinkBindings(canvas)
                self.link = self.linkWidget = None

        # Load links
        links = loadedTopology['links']
        for link in links:
            srcNode = link['src']
            src = self.findWidgetByName(srcNode, canvas)
            sx, sy = canvas.coords( canvas.widgetToItem[ src ] )

            destNode = link['dest']
            dest = self.findWidgetByName(destNode, canvas)
            dx, dy = canvas.coords( canvas.widgetToItem[ dest]  )

            self.link = canvas.create_line( sx, sy, dx, dy, width=4,
                                             fill='blue', tag='link' )
            canvas.itemconfig(self.link, tags=canvas.gettags(self.link)+('data',))
            self.addLink( src, dest, canvas, linkopts=link['opts'] )
            self.createDataLinkBindings(canvas)
            self.link = self.linkWidget = None

        f.close()

    
    def findWidgetByName( self, name, canvas ):
        for widget in canvas.widgetToItem:
            if name ==  widget[ 'text' ]:
                return widget

    def newTopologies(self):
        
        for canvas in [self.nf_canvas, self.phy_canvas]:
            self.newTopology(canvas)

	# Clear the canvases - fresh start
    def newTopology( self, canvas ):
        """New command."""
        for widget in canvas.widgetToItem.keys():
            self.deleteItem( canvas.widgetToItem[ widget ], canvas )
        canvas.hostCount = 0
        canvas.switchCount = 0
        canvas.controllerCount = 0
        canvas.vnfCount = 0
        canvas.startpointCount = 0
        canvas.links = {}
        canvas.hostOpts = {}
        canvas.switchOpts = {}
        canvas.controllers = {}
        canvas.vnfOpts = {}
        canvas.startpointOpts = {}
        self.appPrefs["ipBase"]= self.defaultIpBase

    def saveNFTopology(self):
        self.saveTopology(self.nf_canvas)

    def savePHYTopology(self):
        self.saveTopology(self.phy_canvas)

    
    def saveTopology( self, canvas ):
        """Save command."""
        myFormats = [
            ('Mininet Topology','*.mn'),
            ('All Files','*'),
        ]

        savingDictionary = {}
        fileName = tkFileDialog.asksaveasfilename(filetypes=myFormats ,title="Save the topology as...")
        if len(fileName ) > 0:
            # Save Application preferences
            savingDictionary['version'] = '2'

            # Save Switches and Hosts
            hostsToSave = []
            switchesToSave = []
            controllersToSave = []
            vnfToSave = []
            startpointToSave = []
            for widget in canvas.widgetToItem:
                name = widget[ 'text' ]
                tags = canvas.gettags( canvas.widgetToItem[ widget ] )
                x1, y1 = canvas.coords( canvas.widgetToItem[ widget ] )
                if 'Switch' in tags or 'LegacySwitch' in tags or 'LegacyRouter' in tags:
                    nodeNum = canvas.switchOpts[name]['nodeNum']
                    nodeToSave = {'number':str(nodeNum),
                                  'x':str(x1),
                                  'y':str(y1),
                                  'opts':canvas.switchOpts[name] }
                    switchesToSave.append(nodeToSave)
                elif 'Host' in tags:
                    nodeNum = canvas.hostOpts[name]['nodeNum']
                    nodeToSave = {'number':str(nodeNum),
                                  'x':str(x1),
                                  'y':str(y1),
                                  'opts':canvas.hostOpts[name] }
                    hostsToSave.append(nodeToSave)
                elif 'Controller' in tags:
                    nodeToSave = {'x':str(x1),
                                  'y':str(y1),
                                  'opts':canvas.controllers[name] }
                    controllersToSave.append(nodeToSave)
                elif 'Vnf' in tags:
                    nodeNum = canvas.vnfOpts[name]['nodeNum']
                    nodeToSave = {'number':str(nodeNum),
                                  'x':str(x1),
                                  'y':str(y1),
                                  'opts':canvas.vnfOpts[name] }
                    vnfToSave.append(nodeToSave)
                elif 'Startpoint' in tags:
                    nodeNum = canvas.startpointOpts[name]['nodeNum']
                    nodeToSave = {'number':str(nodeNum),
                                  'x':str(x1),
                                  'y':str(y1),
                                  'opts':canvas.startpointOpts[name] }
                    startpointToSave.append(nodeToSave)
                else:
                    raise Exception( "Cannot create mystery node: " + name )
            savingDictionary['hosts'] = hostsToSave
            savingDictionary['switches'] = switchesToSave
            savingDictionary['controllers'] = controllersToSave
            savingDictionary['vnfs'] = vnfToSave
            savingDictionary['startpoints'] = startpointToSave

            # Save Links
            linksToSave = []
            for link in canvas.links.values():
                src = link['src']
                dst = link['dest']
                linkopts = link['linkOpts']

                srcName, dstName = src[ 'text' ], dst[ 'text' ]
                linkToSave = {'src':srcName,
                              'dest':dstName,
                              'opts':linkopts}
                if link['type'] == 'data':
                    linksToSave.append(linkToSave)
            savingDictionary['links'] = linksToSave

            # Save Application preferences
            #savingDictionary['application'] = self.appPrefs

            with open(fileName, 'wb') as f:
                try:
                    #f.write(str(savingDictionary))
                    f.write(json.dumps(savingDictionary, sort_keys=True, indent=4, separators=(',', ': ')))
                except Exception as er:
                    print er

    # Generic canvas handler
    #
    # We could have used bindtags, as in nodeIcon, but
    # the dynamic approach used here
    # may actually require less code. In any case, it's an
    # interesting introspection-based alternative to bindtags.

    def canvasHandle( self, eventName, event ):
        """Generic canvas event handler"""
        if self.active is None or event.widget.disabled:
            return
        toolName = self.active
        if toolName not in event.widget.available:
            return
        handler = getattr( self, eventName + toolName, None )
        if handler is not None:
            handler( event )

    def clickCanvas( self, event ):
        """Canvas click handler."""
        self.canvasHandle( 'click', event )

    def dragCanvas( self, event ):
        """Canvas drag handler."""
        self.canvasHandle( 'drag', event )

    def releaseCanvas( self, event ):
        """Canvas mouse up handler."""
        self.canvasHandle( 'release', event )

    # Currently the only items we can select directly are
    # links. Nodes are handled by bindings in the node icon.

    
    def  findItem( self, x, y, canvas ):
        """Find items at a location in our canvas."""
        items = canvas.find_overlapping( x, y, x, y )
        if len( items ) == 0:
            return None
        else:
            return items[ 0 ]

    # Canvas bindings for Select, Host, Switch and Link tools

    def clickSelect( self, event ):
        """Select an item."""
        self.selectItem( self.findItem( event.x, event.y, event.widget ), event.widget.master )

    def deleteItem( self, item, canvas ):
        """Delete an item."""
        # Don't delete while network is running
        if self.buttons[ 'Select' ][ 'state' ] == 'disabled':
            return
        # Delete from model
        if item in canvas.links:
            self.deleteLink( item, canvas )
        if item in canvas.itemToWidget:
            self.deleteNode( item, canvas )
        # Delete from view
        canvas.delete( item )

    
    def deleteSelection( self, _event ):
        """Delete the selected item."""
        if self.selection is not None:
            canvas = self.actualCanvas
            self.deleteItem( self.selection, canvas)
        self.selectItem( None, None )

    
    def nodeIcon( self, node_type, name, canvas, options={} ):
        """Create a new node icon."""
        iconname = self.get_iconname(node_type, name, options)
        image = self.images.get(iconname, None)
        icon = Button( canvas, image=image,
                       text=name, compound='top' )
        # Unfortunately bindtags wants a tuple
        bindtags = [ str( self.nodeBindings ) ]
        bindtags += list( icon.bindtags() )
        icon.bindtags( tuple( bindtags ) )
        return icon

    def set_icon(self, node_id, iconname, canvas):
        icon = canvas.itemToWidget[node_id]
        icon.configure(image=self.images[iconname])

    
    def get_iconname(self, node_type, name, options={}):
        """Return the icon for a node using different sources.

        The following sources are checked in order.
        * the 'icon' propery of the VNF.
        * the name of the node.
        """
        if node_type != 'Vnf':
            return node_type

        iconname = name + '.png'
        db = Catalog().get_db()
        vnf_name = options.get('function', name)
        vnf = db.get(vnf_name, {})
        iconname = vnf.get('icon', iconname)

        if iconname in self.images:
            self._debug('Load %s icon from catalog for %s'%(iconname, name))
            return iconname

        filename = resource_path(iconname)
        if os.path.exists(filename):
            self._debug('Load %s icon from file for %s'%(filename, name))
            new_image = ImageTk.PhotoImage(Image.open(filename))
            self.images[iconname] = new_image
            return iconname
        else:
            self._debug('Load default icon for %s: %s' % (name, node_type))
            return node_type

    def updateNodeIcon( self, node_id, name, canvas, options ):
        iconname = self.get_iconname('Vnf', name, options)
        self.set_icon(node_id, iconname, canvas)

    
    def newNode( self, node, event, canvas ):
        """Add a new node to our canvas."""
        x, y = canvas.canvasx( event.x ), canvas.canvasy( event.y )
        name = self.nodePrefixes[ node ]
        _id = self.next_id()
        options = None
        if 'Switch' == node:
            canvas.switchCount += 1
            name = self.nodePrefixes[ node ] + str( canvas.switchCount )
            canvas.switchOpts[name] = {}
            canvas.switchOpts[name]['nodeNum']=canvas.switchCount
            canvas.switchOpts[name]['hostname']=name
            canvas.switchOpts[name]['switchType']='default'
            canvas.switchOpts[name]['controllers']=[]
            canvas.switchOpts[name]['node_type'] = self.TYPE_SWITCH
            canvas.switchOpts[name]['res'] = {}
            canvas.switchOpts[name]['res']['cpu'] = 0
            canvas.switchOpts[name]['res']['mem'] = 0
            canvas.switchOpts[name]['_id'] = _id
            options = canvas.switchOpts[name]
        if 'LegacyRouter' == node:
            canvas.switchCount += 1
            name = self.nodePrefixes[ node ] + str( canvas.switchCount )
            canvas.switchOpts[name] = {}
            canvas.switchOpts[name]['nodeNum']=canvas.switchCount
            canvas.switchOpts[name]['hostname']=name
            canvas.switchOpts[name]['switchType']='legacyRouter'
            canvas.switchOpts[name]['node_type'] = self.TYPE_SWITCH
            canvas.switchOpts[name]['res'] = {}
            canvas.switchOpts[name]['res']['cpu'] = 0
            canvas.switchOpts[name]['res']['mem'] = 0
            canvas.switchOpts[name]['_id'] = _id
            options = canvas.switchOpts[name]
        if 'LegacySwitch' == node:
            canvas.switchCount += 1
            name = self.nodePrefixes[ node ] + str( canvas.switchCount )
            canvas.switchOpts[name] = {}
            canvas.switchOpts[name]['nodeNum']=canvas.switchCount
            canvas.switchOpts[name]['hostname']=name
            canvas.switchOpts[name]['switchType']='legacySwitch'
            canvas.switchOpts[name]['controllers']=[]
            canvas.switchOpts[name]['node_type'] = self.TYPE_SWITCH
            canvas.switchOpts[name]['res'] = {}
            canvas.switchOpts[name]['res']['cpu'] = 0
            canvas.switchOpts[name]['res']['mem'] = 0
            canvas.switchOpts[name]['_id'] = _id
            options = canvas.switchOpts[name]
        if 'Host' == node:
            canvas.hostCount += 1
            name = self.nodePrefixes[ node ] + str( canvas.hostCount )
            canvas.hostOpts[name] = {'sched':'host'}
            canvas.hostOpts[name]['nodeNum']=canvas.hostCount
            canvas.hostOpts[name]['hostname']=name
            canvas.hostOpts[name]['node_type'] = self.TYPE_HOST
            canvas.hostOpts[name]['ee_type'] = 'static'
            canvas.hostOpts[name]['res'] = {}
            # Why these are the default values?
            canvas.hostOpts[name]['res']['cpu'] = 0.8
            canvas.hostOpts[name]['res']['mem'] = 0.1
            canvas.hostOpts[name]['_id'] = _id
            options = canvas.hostOpts[name]
        if 'Controller' == node:
            name = self.nodePrefixes[ node ] + str( canvas.controllerCount )
            ctrlr = { 'controllerType': 'remote',
                      'hostname': name,
                      'remoteIP': '127.0.0.1',
                      'remotePort': 6633,
                      '_id': _id,
                      'node_type' : self.TYPE_CONTROLLER}
            canvas.controllers[name] = ctrlr
            options = canvas.controllers[name]
            # We want to start controller count at 0
            canvas.controllerCount += 1
        if 'Vnf' == node:
            canvas.vnfCount += 1
            name = self.nodePrefixes[ node ] + str( canvas.vnfCount )
            name = 'VNF' + str( canvas.vnfCount )
            canvas.vnfOpts[name] = {'nodeNum':canvas.vnfCount}
            canvas.vnfOpts[name]['name']=name
            canvas.vnfOpts[name]['node_type'] = self.TYPE_FUNCTION
            canvas.vnfOpts[name]['req'] = {}
            canvas.vnfOpts[name]['req']['cpu'] = 0.8
            canvas.vnfOpts[name]['req']['mem'] = 0.1
            canvas.vnfOpts[name]['function'] = 'headerCompressor'
            canvas.vnfOpts[name]['vnf_type'] = 'click_vnf'
            canvas.vnfOpts[name]['_id'] = _id
            # canvas.vnfOpts[name]['custom_params'] = {}
            options = canvas.vnfOpts[name]

        if 'Startpoint' == node:
            canvas.startpointCount += 1
            name = self.nodePrefixes[ node ] + str( canvas.startpointCount )
            canvas.startpointOpts[name] = {'nodeNum':canvas.startpointCount}
            canvas.startpointOpts[name]['name']=name
            canvas.startpointOpts[name]['node_type'] = self.TYPE_ENDPOINT
            canvas.startpointOpts[name]['_id'] = _id
            options = canvas.startpointOpts[name]

        icon = self.nodeIcon( node, name, canvas, options )
        item = canvas.create_window( x, y, anchor=CENTER, window=icon,
                                          tags=node )
        canvas.widgetToItem[ icon ] = item
        canvas.itemToWidget[ item ] = icon
        canvas.idToWidget[ _id ] = icon
        canvas.nameToWidget[name] = icon
        self.selectItem( item, canvas )
        icon.links = {}
        if 'Switch' == node:
            icon.bind('<Button-3>', self.do_switchPopup )
        if 'LegacyRouter' == node:
            icon.bind('<Button-3>', self.do_legacyRouterPopup )
        if 'LegacySwitch' == node:
            icon.bind('<Button-3>', self.do_legacySwitchPopup )
        if 'Host' == node:
            icon.bind('<Button-3>', self.do_hostPopup )
        if 'Controller' == node:
            icon.bind('<Button-3>', self.do_controllerPopup )
        if 'Vnf' == node:
            icon.bind('<Button-3>', self.do_vnfPopup )
        if 'Startpoint' == node:
            icon.bind('<Button-3>', self.do_startpointPopup )

        self.updateGraphNode(name, options, canvas, item)

    def clickController( self, event ):
        """Add a new Controller to our canvas."""
        self.newNode( 'Controller', event, event.widget )

    def clickHost( self, event ):
        """Add a new host to our canvas."""
        self.newNode( 'Host', event, event.widget )

    def clickVnf( self, event ):
        """Add a new vnf to our canvas."""
        self.newNode( 'Vnf', event, event.widget )

    def clickStartpoint( self, event ):
        """Add a new start/endpoint to our canvas."""
        self.newNode( 'Startpoint', event, event.widget )

    def clickLegacyRouter( self, event ):
        """Add a new switch to our canvas."""
        self.newNode( 'LegacyRouter', event, event.widget )

    def clickLegacySwitch( self, event ):
        """Add a new switch to our canvas."""
        self.newNode( 'LegacySwitch', event, event.widget )

    def clickSwitch( self, event ):
        """Add a new switch to our canvas."""
        self.newNode( 'Switch', event, event.widget )

    def dragNetLink( self, event ):
        """Drag a link's endpoint to another node."""
        if self.link is None:
            return
        canvas = event.widget.master
        # Since drag starts in widget, we use root coords
        x = self.canvasx( event.x_root, canvas )
        y = self.canvasy( event.y_root, canvas )
        canvas.coords( self.link, self.linkx, self.linky, x, y )

    
    def releaseNetLink_( self, _event, canvas ):
        """Give up on the current link."""
        if self.link is not None:
            canvas.delete( self.link )
        self.linkWidget = self.linkItem = self.link = None

    # Generic node handlers

    def createNodeBindings( self ):
        """Create a set of bindings for nodes."""
        bindings = {
            '<ButtonPress-1>': self.clickNode,
            '<B1-Motion>': self.dragNode,
            '<ButtonRelease-1>': self.releaseNode,
            '<Enter>': self.enterNode,
            '<Leave>': self.leaveNode
        }
        l = Label()  # lightweight-ish owner for bindings
        for event, binding in bindings.items():
            l.bind( event, binding )
        return l

    def selectItem( self, item, canvas ):
        """Select an item and remember old selection."""
        self.lastSelection = self.selection
        
        self.lastCanvas = self.actualCanvas
        self.selection = item
        self.actualCanvas = canvas

    def enterNode( self, event ):
        """Select node on entry."""
        self.selectNode( event )

    def leaveNode( self, _event ):
        """Restore old selection on exit."""
        self.selectItem( self.lastSelection, _event.widget.master )

    def clickNode( self, event ):
        """Node click handler."""
        if event.widget.master.disabled: #parent canvas
            return
        if self.active is 'NetLink':
            self.startLink( event )
        else:
            self.selectNode( event )
        return 'break'

    def dragNode( self, event ):
        """Node drag handler."""
        if self.active is 'NetLink':
            self.dragNetLink( event)
        else:
            self.dragNodeAround( event )

    def releaseNode( self, event ):
        """Node release handler."""
        if event.widget.master.disabled: #parent canvas
            return
        if self.active is 'NetLink':
            self.finishLink( event )


    # Specific node handlers

    def selectNode( self, event ):
        """Select the node that was clicked on."""
        canvas = event.widget.master
        item = canvas.widgetToItem.get( event.widget, None )
        self.selectItem( item, canvas )

    def dragNodeAround( self, event ):
        """Drag a node around on the canvas."""
        canvas = event.widget.master
        # Convert global to local coordinates;
        # Necessary since x, y are widget-relative
        x = self.canvasx( event.x_root, canvas )
        y = self.canvasy( event.y_root, canvas )
        w = event.widget
        # Adjust node position
        item = canvas.widgetToItem[ w ]
        canvas.coords( item, x, y )
        if getattr(w,'upper_info', None): canvas.coords( w.upper_info, x, y-w.winfo_height()/2 - 5)
        if getattr(w,'upper_info', None): canvas.coords( w.lower_info, x, y+w.winfo_height()/2 + 5)
        # Adjust link positions
        for dest in w.links:
            link = w.links[ dest ]
            item = canvas.widgetToItem[ dest ]
            x1, y1 = canvas.coords( item )
            canvas.coords( link, x, y, x1, y1 )
        self.updateScrollRegion(canvas)

    def createControlLinkBindings( self, canvas ):
        """Create a set of bindings for nodes."""
        # Link bindings
        # Selection still needs a bit of work overall
        # Callbacks ignore event

        def select( _event, link=self.link ):
            """Select item on mouse entry."""
            self.selectItem( link, _event.widget )

        def highlight( _event, link=self.link ):
            """Highlight item on mouse entry."""
            self.selectItem( link, _event.widget )
            canvas.itemconfig( link, fill='#33ccff' )

        
        def unhighlight( _event, link=self.link ):
            """Unhighlight item on mouse exit."""
            canvas.itemconfig( link, fill='red' )
            #self.selectItem( None )

        canvas.tag_bind( self.link, '<Enter>', highlight )
        canvas.tag_bind( self.link, '<Leave>', unhighlight )
        canvas.tag_bind( self.link, '<ButtonPress-1>', select )

    
    def highlight_route(self, route_tag, canvas, color):
        items = canvas.find_withtag(route_tag)
        for item in items:
            old_color = canvas.links[item].get('old_color', None)
            if not old_color:
                old_color = canvas.itemcget(item, 'fill')
            canvas.links[item]['old_color'] = old_color
            canvas.itemconfig(item, dash = (3,3), fill = color)

    
    def unhighlight_route(self, route_tag, canvas):
        items = canvas.find_withtag(route_tag)
        for item in items:
            old_color = canvas.links[item].get('old_color', None)
            if not old_color: continue #already reverted
            canvas.itemconfig(item, dash = (), fill = old_color)
            del canvas.links[item]['old_color']

    def next_color(self):
        self.color_index = (self.color_index + 1)%len(TK_COLORS)
        return TK_COLORS[self.color_index]

    def createDataLinkBindings( self, canvas ):
        """Create a set of bindings for nodes."""
        # Link bindings
        # Selection still needs a bit of work overall
        # Callbacks ignore event
        regex = re.compile('route[1-9]*')

        def select( _event, link=self.link ):
            """Select item on mouse entry."""
            self.selectItem( link, _event.widget )

        def highlight( _event, link=self.link ):
            """Highlight item on mouse entry."""
            self.selectItem( link, _event.widget )
            self.color_index = 0
            color = '#33ccff'

            route_tags = filter(regex.match, canvas.gettags(link))
            if not route_tags:
                canvas.links[link]['old_color'] = canvas.itemcget(link, 'fill')
                canvas.itemconfig( link, fill=color )
            for route_tag in route_tags:
                color = self.next_color()
                self.highlight_route(route_tag, self.nf_canvas, color)
                self.highlight_route(route_tag, self.phy_canvas, color)


        
        def unhighlight( _event, link=self.link ):
            """Unhighlight item on mouse exit."""
            route_tags = filter(regex.match, canvas.gettags(link))
            if not route_tags:
                color = getattr(link, 'old_color', 'blue')
                self.old_color = None
                canvas.itemconfig( link, fill=color )

            for route_tag in route_tags:
                self.unhighlight_route(route_tag, self.nf_canvas)
                self.unhighlight_route(route_tag, self.phy_canvas)
            #self.selectItem( None )

        canvas.tag_bind( self.link, '<Enter>', highlight )
        canvas.tag_bind( self.link, '<Leave>', unhighlight )
        canvas.tag_bind( self.link, '<ButtonPress-1>', select )
        canvas.tag_bind( self.link, '<Button-3>', self.do_linkPopup )

    def startLink( self, event ):
        """Start a new link."""
        canvas = event.widget.master
        if event.widget not in canvas.widgetToItem:
            # Didn't click on a node
            return
        w = event.widget
        item = canvas.widgetToItem[ w ]
        x, y = canvas.coords( item )
        self.link = canvas.create_line( x, y, x, y, width=4,
                                             fill='blue', tag='link' )
        self.linkx, self.linky = x, y
        self.linkWidget = w
        self.linkItem = item

    def finishLink( self, event ):
        """Finish creating a link"""
        if self.link is None:
            return
        source = self.linkWidget
        canvas = event.widget.master
        # Since we dragged from the widget, use root coords
        x, y = self.canvasx( event.x_root, canvas ), self.canvasy( event.y_root, canvas )
        target = self.findItem( x, y, canvas )
        dest = canvas.itemToWidget.get( target, None )
        if ( source is None or dest is None or source == dest
                or dest in source.links or source in dest.links ):
            self.releaseNetLink_( event, canvas )
            return
        # For now, don't allow hosts to be directly linked
        stags = canvas.gettags( canvas.widgetToItem[ source ] )
        dtags = canvas.gettags( target )
        if (('Host' in stags and 'Host' in dtags) or
           ('Controller' in dtags and 'LegacyRouter' in stags) or
           ('Controller' in stags and 'LegacyRouter' in dtags) or
           ('Controller' in dtags and 'LegacySwitch' in stags) or
           ('Controller' in stags and 'LegacySwitch' in dtags) or
           ('Controller' in dtags and 'Startpoint' in stags) or
           ('Controller' in stags and 'Startpoint' in dtags) or
           ('Controller' in dtags and 'Vnf' in stags) or
           ('Controller' in stags and 'Vnf' in dtags) or
           ('Controller' in dtags and 'Host' in stags) or
           ('Controller' in stags and 'Host' in dtags) or
           ('Controller' in stags and 'Controller' in dtags)):
            self.releaseNetLink_( event, canvas )
            return

        # Set link type
        linkType='data'
        if 'Controller' in stags or 'Controller' in dtags:
            linkType='control'
            canvas.itemconfig(self.link, dash=(6, 4, 2, 4), fill='red')
            self.createControlLinkBindings(canvas)
        else:
            linkType='data'
            self.createDataLinkBindings(canvas)
        canvas.itemconfig(self.link, tags=canvas.gettags(self.link)+(linkType,))

        x, y = canvas.coords( target )
        canvas.coords( self.link, self.linkx, self.linky, x, y )
        self.addLink( source, dest, canvas, linktype=linkType )
        if linkType == 'control':
            controllerName = ''
            switchName = ''
            if 'Controller' in stags:
                controllerName = source[ 'text' ]
                switchName = dest[ 'text' ]
            else:
                controllerName = dest[ 'text' ]
                switchName = source[ 'text' ]

            canvas.switchOpts[switchName]['controllers'].append(controllerName)

        # We're done
        self.link = self.linkWidget = None


    # Menu handlers

    
    def createToolImages( self ):
        """Create toolbar (and icon) images."""

    
    def checkIntf( self, intf ):
        """Make sure intf exists and is not configured."""
        if ( ' %s:' % intf ) not in quietRun( 'ip link show' ):
            tkMessageBox.showerror(title="Error",
                      message='External interface ' +intf + ' does not exist! Skipping.')
            return False
        ips = re.findall( r'\d+\.\d+\.\d+\.\d+', quietRun( 'ifconfig ' + intf ) )
        if ips:
            tkMessageBox.showerror(title="Error",
                      message= intf + ' has an IP address and is probably in use! Skipping.' )
            return False
        return True

    
    def updateOptions( self, opts, opt_list, values):
        for opt, opt_type in opt_list:
            if len(values.get(opt, '')) > 0:
                opts[opt] = opt_type( values.get(opt) )

    
    def hostDetails( self, canvas, _ignore=None ):
        if ( self.selection is None or
             self.net is not None or
             self.selection not in canvas.itemToWidget ):
            return
        widget = canvas.itemToWidget[ self.selection ]
        old_name = widget[ 'text' ]
        tags = canvas.gettags( self.selection )
        if 'Host' not in tags:
            return

        opts = canvas.hostOpts[old_name]
        hostBox = HostDialog(self, title='Host Details', prefDefaults=opts)
        self.master.wait_window(hostBox.top)
        if not hostBox.result:
            return

        opt_list = [ ('hostname', str),
                     ('cores', int),
                     ('sched', str),
                     ('ee_type', str),
                     ('remote_dpid', str),
                     ('remote_port', int),
                     ('remote_conf_ip', str),
                     ('remote_netconf_port', int),
                     ('netconf_username', str),
                     ('netconf_passwd', str),
                     ('local_intf_name', str),
                     ('mem', float),
                     ('cpu', float),
                     ('defaultRoute', str),
                     ('ip', str),
                     ('externalInterfaces', list),
                     ('vlanInterfaces', list)
                     ]
        self.updateOptions(opts, opt_list, hostBox.result)
        opt_list = [ ('mem', float),
                     ('cpu', float),
                     ]
        self.updateOptions(opts['res'], opt_list, hostBox.result)

        name = opts['hostname']
        widget[ 'text' ] = name

        del canvas.hostOpts[old_name]
        canvas.hostOpts[name] = opts

        if old_name == name: old_name = None
        self.updateGraphNode(name, opts, canvas,
                             canvas.widgetToItem[widget], old_name=old_name)

        #self.updateGraphNode(name, opts, canvas, self.selection)
        self._debug('New host details for %s = %s'%(name, str(opts)))

    
    def vnfDetails( self, canvas, _ignore=None ):
        if ( self.selection is None or
             self.selection not in canvas.itemToWidget ):
            return
        widget = canvas.itemToWidget[ self.selection ]
        old_name = widget[ 'text' ]

        opts = canvas.vnfOpts[old_name]
        vnfBox = VnfDialog(self, title='VNF Details', prefDefaults=opts)
        self.master.wait_window(vnfBox.top)

        if not vnfBox.result:
            return

        opt_list = [ ('name', str),
                     ('function', str),
                     ('mem', float),
                     ('cpu', float)]
        self.updateOptions(opts, opt_list, vnfBox.result)
        opt_list = [ ('mem', float),
                     ('cpu', float)]
        self.updateOptions(opts['req'], opt_list, vnfBox.result)

        name = opts['name']
        widget[ 'text' ] = name

        del canvas.vnfOpts[old_name]
        canvas.vnfOpts[name] = opts
        if old_name == name: old_name = None
        self.updateGraphNode(name, opts, canvas,
                             canvas.widgetToItem[widget],
                             old_name = old_name)
        self._debug('New VNF details for %s = %s'%(name, str(opts)))

    
    def startpointDetails( self, canvas, _ignore=None ):
        if ( self.selection is None or
             self.selection not in canvas.itemToWidget ):
            return
        widget = canvas.itemToWidget[ self.selection ]
        old_name = widget[ 'text' ]

        opts = canvas.startpointOpts[old_name]
        dialog = StartpointDialog(self, title='Startpoint Details',
                                  prefDefaults=opts)
        self.master.wait_window(dialog.top)
        if not dialog.result:
            return

        opt_list = [ ('name', str) ]
        self.updateOptions(opts, opt_list, dialog.result)

        name = opts['name']
        widget[ 'text' ] = name

        del canvas.startpointOpts[old_name]
        canvas.startpointOpts[name] = opts

        if old_name == name: old_name = None
        self.updateGraphNode(name, opts, canvas, self.selection,
                             old_name=old_name)
        self._debug('New startpoint details for %s = %s' % (name, str(opts)))

    
    def switchDetails( self, canvas,  _ignore=None):
        if ( self.selection is None or
             self.net is not None or
             self.selection not in canvas.itemToWidget ):
            return
        widget = canvas.itemToWidget[ self.selection ]
        name = widget[ 'text' ]
#         tags = canvas.gettags( self.selection )
#         if 'Switch' not in tags:
#             return

        prefDefaults = canvas.switchOpts[name]
        switchBox = SwitchDialog(self, title='Switch Details', prefDefaults=prefDefaults)
        self.master.wait_window(switchBox.top)
        if switchBox.result:
            newSwitchOpts = {'nodeNum': canvas.switchOpts[name]['nodeNum'], 'node_type': self.TYPE_SWITCH,
                             'switchType': switchBox.result['switchType'],
                             'controllers': canvas.switchOpts[name]['controllers']}
            if len(switchBox.result['dpctl']) > 0:
                newSwitchOpts['dpctl'] = switchBox.result['dpctl']
            if len(switchBox.result['dpid']) > 0:
                newSwitchOpts['dpid'] = switchBox.result['dpid']
            if len(switchBox.result['hostname']) > 0:
                newSwitchOpts['hostname'] = switchBox.result['hostname']
                name = switchBox.result['hostname']
                widget[ 'text' ] = name
            if len(switchBox.result['externalInterfaces']) > 0:
                newSwitchOpts['externalInterfaces'] = switchBox.result['externalInterfaces']
            newSwitchOpts['switchIP'] = switchBox.result['switchIP']
            newSwitchOpts['sflow'] = switchBox.result['sflow']
            newSwitchOpts['netflow'] = switchBox.result['netflow']
            old_name = prefDefaults['hostname'] if prefDefaults['hostname'] != newSwitchOpts['hostname'] else None
            canvas.switchOpts[name].update(newSwitchOpts)
            self.updateGraphNode(name, canvas.switchOpts[name], canvas, self.selection, old_name = old_name)
            self._debug('New switch details for %s = %s'%(name, str(newSwitchOpts)))

    def linkUp( self, canvas ):
        if ( self.selection is None or
             self.net is None):
            return
        link = self.selection
        linkDetail =  canvas.links[link]
        src = linkDetail['src']
        dst = linkDetail['dest']
        srcName, dstName = src[ 'text' ], dst[ 'text' ]
        self.net.configLinkStatus(srcName, dstName, 'up')
        canvas.itemconfig(link, dash=())

    def linkDown( self, canvas ):
        if ( self.selection is None or
             self.net is None):
            return
        link = self.selection
        linkDetail =  canvas.links[link]
        src = linkDetail['src']
        dst = linkDetail['dest']
        srcName, dstName = src[ 'text' ], dst[ 'text' ]
        self.net.configLinkStatus(srcName, dstName, 'down')
        canvas.itemconfig(link, dash=(4, 4))

    def linkDetails( self, canvas, _ignore=None ):
        if ( self.selection is None or
             self.net is not None):
            return
        link = self.selection

        linkDetail =  canvas.links[link]
        src = linkDetail['src']
        dest = linkDetail['dest']
        pair = canvas.links.get( link, None )
        src_name = pair['src']['text']
        dest_name = pair['dest']['text']
        linkopts = linkDetail['linkOpts']
        linkBox = LinkDialog(self, title='Link Details', linkDefaults=linkopts)
        if linkBox.result is not None:
            linkDetail['linkOpts'].update(linkBox.result)
            self.updateGraphEdge(src_name, dest_name, linkDetail['linkOpts'], canvas)
            self._debug('New link details = %s'%(str(linkDetail['linkOpts'])))

    def prefDetails( self ):
        prefDefaults = self.appPrefs
        prefBox = PrefsDialog(self, title='Preferences', prefDefaults=prefDefaults)
        self._debug('New Prefs = %s'%(str(prefBox.result)))
        if prefBox.result:
            self.appPrefs = prefBox.result


    def controllerDetails( self, canvas ):
        if ( self.selection is None or
             self.net is not None or
             self.selection not in canvas.itemToWidget ):
            return
        widget = canvas.itemToWidget[ self.selection ]
        name = widget[ 'text' ]
#         tags = canvas.gettags( self.selection )
        oldName = name
#         if 'Controller' not in tags:
#             return

        ctrlrBox = ControllerDialog(self, title='Controller Details', ctrlrDefaults=canvas.controllers[name])
        if ctrlrBox.result:
            self._debug('New controller options: %s'% ctrlrBox.result)
            if len(ctrlrBox.result['hostname']) > 0:
                name = ctrlrBox.result['hostname']
                widget[ 'text' ] = name
            else:
                ctrlrBox.result['hostname'] = name
            canvas.controllers[oldName].update(ctrlrBox.result)
            # Find references to controller and change name
            if oldName != name:
                canvas.controllers[name] = canvas.controllers[oldName]
                del canvas.controllers[oldName]
                for widget in canvas.widgetToItem:
                    switchName = widget[ 'text' ]
                    tags = canvas.gettags( canvas.widgetToItem[ widget ] )
                    if 'Switch' in tags:
                        switch = canvas.switchOpts[switchName]
                        if oldName in switch['controllers']:
                            switch['controllers'].remove(oldName)
                            switch['controllers'].append(name)

            self._debug('New controller details for %s = %s'%(name, str(canvas.controllers[name])))
            old_name = oldName if oldName != name else None
            self.updateGraphNode(name, canvas.controllers[name], canvas, self.selection, old_name = old_name)


    
    def listBridge( self, canvas, _ignore=None):
        if ( self.selection is None or
             self.net is None or
             self.selection not in canvas.itemToWidget ):
            return
        name = canvas.itemToWidget[ self.selection ][ 'text' ]
        tags = canvas.gettags( self.selection )

        if name not in self.net.nameToNode:
            return
        if 'Switch' in tags or 'LegacySwitch' in tags:
           call(["xterm -T 'Bridge Details' -sb -sl 2000 -e 'ovs-vsctl list bridge " + name + "; read -p \"Press Enter to close\"' &"], shell=True)

    def ovsShow( self, _ignore=None ):
        call(["xterm -T 'OVS Summary' -sb -sl 2000 -e 'ovs-vsctl show; read -p \"Press Enter to close\"' &"], shell=True)

    def rootTerminal( self, _ignore=None ):
        call(["xterm -T 'Root Terminal' -sb -sl 2000 &"], shell=True)

    
    def startCLI( self, _ignore=None ):
        if self.net is not None:
            cli.CLI(self.net)

    # Model interface
    #
    # Ultimately we will either want to use a topo or
    # mininet object here, probably.

    def addLink(self, source, dest, canvas, linktype='data', linkopts=None):
        """Add link to model."""
        if not linkopts:
            linkopts = {}
        source.links[ dest ] = self.link
        dest.links[ source ] = self.link
        canvas.links[ self.link ] = {'type' :linktype,
                                   'src':source,
                                   'dest':dest,
                                   'linkOpts':linkopts}

        self.updateGraphEdge(source['text'], dest['text'], canvas.links[self.link], canvas)

    def deleteLink( self, link, canvas ):
        """Delete link from model."""
        pair = canvas.links.get( link, None )
        if pair is not None:
            source=pair['src']
            dest=pair['dest']
            del source.links[ dest ]
            del dest.links[ source ]
            stags = canvas.gettags( canvas.widgetToItem[ source ] )
            dtags = canvas.gettags( canvas.widgetToItem[ dest ] )
            ltags = canvas.gettags( link )

            self.removeGraphEdge(source[ 'text' ], dest[ 'text' ], canvas)

            if 'control' in ltags:
                controllerName = ''
                switchName = ''
                if 'Controller' in stags:
                    controllerName = source[ 'text' ]
                    switchName = dest[ 'text' ]
                else:
                    controllerName = dest[ 'text' ]
                    switchName = source[ 'text' ]

                if controllerName in canvas.switchOpts[switchName]['controllers']:
                    canvas.switchOpts[switchName]['controllers'].remove(controllerName)


        if link is not None:
            del canvas.links[ link ]

    def deleteNode( self, item, canvas ):
        """Delete node (and its links) from model."""

        widget = canvas.itemToWidget[ item ]
        tags = canvas.gettags(item)
        if 'Controller' in tags:
            # remove from switch controller lists
            for serachwidget in canvas.widgetToItem:
                name = serachwidget[ 'text' ]
                tags = canvas.gettags( canvas.widgetToItem[ serachwidget ] )
                if 'Switch' in tags:
                    if widget['text'] in canvas.switchOpts[name]['controllers']:
                        canvas.switchOpts[name]['controllers'].remove(widget['text'])

        for link in widget.links.values():
            # Delete from view and model
            self.deleteItem( link, canvas )

        self.removeGraphNode(widget['text'], canvas)
        if getattr(widget,'upper_info', None): canvas.delete(widget.upper_info)
        if getattr(widget,'lower_info', None): canvas.delete(widget.lower_info)
        del canvas.itemToWidget[ item ]
        del canvas.widgetToItem[ widget ]

    # Do the actual start physical operation
    def start_network(self, phy_g, appPrefs):
        """Start network."""

        #dump(self.nf_canvas)
        if not self.network_manager.network_alive():
            self.network_manager.build_topo(phy_g, appPrefs)
            nflow = self.appPrefs['netflow']
            sflow = self.appPrefs['sflow']
            startcli = self.appPrefs['startCLI']

            self.network_manager.start_topo(nflow = nflow, sflow = sflow, startcli = startcli)
            self.net = self.network_manager.net
            self.node_manager.set_mininet(self.network_manager.net)

    # Do the actual stop physical operation
    def stop_network( self ):
        """Stop network."""
        self._info('Stop network')
        self.node_manager.stop()
        if self.network_manager.network_alive():
            self.network_manager.stop_network()
        # self.node_manager.stop()
        cleanUpScreens()
        self.net = None

    def do_linkPopup(self, event):
        # display the popup menu
        if self.net is None:
            try:
                self.linkPopup.canvas = event.widget
                self.linkPopup.tk_popup(event.x_root, event.y_root, 0)
            finally:
                # make sure to release the grab (Tk 8.0a1 only)
                self.linkPopup.grab_release()
        else:
            try:
                self.linkRunPopup.canvas = event.widget
                self.linkRunPopup.tk_popup(event.x_root, event.y_root, 0)
            finally:
                # make sure to release the grab (Tk 8.0a1 only)
                self.linkRunPopup.grab_release()

    def do_controllerPopup(self, event):
        # display the popup menu
        if self.net is None:
            try:
                self.controllerPopup.canvas = event.widget.master
                self.controllerPopup.tk_popup(event.x_root, event.y_root, 0)
            finally:
                # make sure to release the grab (Tk 8.0a1 only)
                self.controllerPopup.grab_release()

    def do_legacyRouterPopup(self, event):
        # display the popup menu
        if self.net is not None:
            try:
                self.legacyRouterRunPopup.canvas = event.widget.master
                self.legacyRouterRunPopup.tk_popup(event.x_root, event.y_root, 0)
            finally:
                # make sure to release the grab (Tk 8.0a1 only)
                self.legacyRouterRunPopup.grab_release()

    def do_hostPopup(self, event):
        # display the popup menu
        if self.net is None:
            try:
                self.hostPopup.canvas = event.widget.master
                self.hostPopup.tk_popup(event.x_root, event.y_root, 0)
            finally:
                # make sure to release the grab (Tk 8.0a1 only)
                self.hostPopup.grab_release()
        else:
            try:
                self.hostRunPopup.canvas = event.widget.master
                self.hostRunPopup.tk_popup(event.x_root, event.y_root, 0)
            finally:
                # make sure to release the grab (Tk 8.0a1 only)
                self.hostRunPopup.grab_release()

    def do_startpointPopup(self, event):
        # display the popup menu
        if not event.widget.master.disabled: #parent canvas enabled
            try:
                self.startpointPopup.canvas = event.widget.master
                self.startpointPopup.tk_popup(event.x_root, event.y_root, 0)
            finally:
                # make sure to release the grab (Tk 8.0a1 only)
                self.startpointPopup.grab_release()
        else:
            try:
                self.startpointRunPopup.canvas = event.widget.master
                self.startpointRunPopup.tk_popup(event.x_root, event.y_root, 0)
            finally:
                # make sure to release the grab (Tk 8.0a1 only)
                self.startpointRunPopup.grab_release()

    def do_vnfPopup(self, event):
        # display the popup menu
        if not event.widget.master.disabled: #parent canvas enabled
            try:
                self.vnfPopup.canvas = event.widget.master
                self.vnfPopup.tk_popup(event.x_root, event.y_root, 0)
            finally:
                # make sure to release the grab (Tk 8.0a1 only)
                self.vnfPopup.grab_release()
        else:
            try:
                self.vnfRunPopup.canvas = event.widget.master
                self.vnfRunPopup.tk_popup(event.x_root, event.y_root, 0)
            finally:
                # make sure to release the grab (Tk 8.0a1 only)
                self.vnfRunPopup.grab_release()

    def do_legacySwitchPopup(self, event):
        # display the popup menu
        if self.net is not None:
            self.switchRunPopup.canvas = event.widget.master
            try:
                self.switchRunPopup.tk_popup(event.x_root, event.y_root, 0)
            finally:
                # make sure to release the grab (Tk 8.0a1 only)
                self.switchRunPopup.grab_release()

    def do_switchPopup(self, event):
        # display the popup menu
        if self.net is None:
            try:
                self.switchPopup.canvas = event.widget.master
                self.switchPopup.tk_popup(event.x_root, event.y_root, 0)
            finally:
                # make sure to release the grab (Tk 8.0a1 only)
                self.switchPopup.grab_release()
        else:
            try:
                self.switchRunPopup.canvas = event.widget.master
                self.switchRunPopup.tk_popup(event.x_root, event.y_root, 0)
            finally:
                # make sure to release the grab (Tk 8.0a1 only)
                self.switchRunPopup.grab_release()

    def start_clicky(self, canvas, _ignore=None):
        if ( self.selection is None or
             self.net is None or
             self.selection not in canvas.itemToWidget ):
            return
        w = canvas.itemToWidget[ self.selection ]
        try:
            name = w.parent_vnf
        except AttributeError:
            tkMessageBox.showerror(title="Error",
                      message="This EE does not run a click instance")
            return
        self._info("Open clickgui on node %s"% name)
        node = self.net.nameToNode[ name ]
        vnf_name = w['text']

        # start clicky directly for VNFs running on netconf node
        container = self.phy_g.node.get(name, {})
        type = container.get('node_type')
        ee_type = container.get('ee_type')
        if type == self.TYPE_HOST and ee_type in ['netconf']:
            from mininet.clickgui import defaultCcssFile
            vnf_options = self.network_manager.vnf_manager.vnf_options.get(vnf_name)
            vnf_control_port = vnf_options['vnf_control_port']
            vnf_control_ip = '127.0.0.1'
            ccssfile = defaultCcssFile()
            call(['clicky -s ' + ccssfile + ' -p '+ vnf_control_ip + ':' + 
                  vnf_control_port + ' &'], shell=True )
        else:
            self.network_manager.start_clicky(vnf_name)

    
    def xterm( self, canvas, _ignore=None ):

        """Make an xterm when a button is pressed."""
        if ( self.selection is None or
             self.net is None or
             self.selection not in canvas.itemToWidget ):
            return
        w = canvas.itemToWidget[ self.selection ]
        name = w[ 'text' ]
        if name not in self.net.nameToNode:
            return
        self._info("Start xterm on node %s"% name)
        term = makeTerm( self.net.nameToNode[ name ], 'Host', term=self.appPrefs['terminalType'] )
        if StrictVersion(VERSION) > StrictVersion('2.0'):
            self.net.terms += term
        else:
            self.net.terms.append(term)

    
    def iperf( self, canvas, _ignore=None ):
        """Make an xterm when a button is pressed."""
        if ( self.selection is None or
             self.net is None or
             self.selection not in canvas.itemToWidget ):
            return
        name = canvas.itemToWidget[ self.selection ][ 'text' ]
        if name not in self.net.nameToNode:
            return
        self.net.nameToNode[ name ].cmd( 'iperf -s -p 5001 &' )

    """ BELOW HERE IS THE TOPOLOGY IMPORT CODE """

    
    def refreshPhyGui(self, canvas):
        # Get host infos
        if self.net is None:
            return

        
        self.mem_total = float( quietRun( self.vnf_mcmd ).split()[-2] )
        for widget in canvas.widgetToItem:
            name = widget[ 'text' ]
            tags = canvas.gettags( canvas.widgetToItem[ widget ] )
            if 'Host' in tags:
#                 self._debug('Get mininet object for host %s'%(name))
                if self.net is None:
                    return
                mininet_host = self.net.get(name)
                ip = mininet_host.IP()
                mac = mininet_host.MAC()

                procresult = quietRun( self.vnf_proc_cmd ).split()
                cpu_total = sum( map(int, procresult[1:10]) )
                cpu_usage = mininet_host.cGetCpuUsage()
                mininet_host.cpu_usage_rel = float(cpu_usage-mininet_host.last_cpu_usage)/float(mininet_host.frac*(cpu_total-mininet_host.last_cpu_total))

                mininet_host.last_cpu_usage = cpu_usage
                mininet_host.last_cpu_total = cpu_total

                mem_usage = mininet_host.cGetMemUsage()
                mininet_host.mem_usage_abs = float(mem_usage)/self.mem_total

                #update info fields
                upper_text = 'IP:%s'% ip + '\n' + 'CPU: %3.1f%%'%(100*mininet_host.cpu_usage_rel)
                lower_text = 'MAC:%s'% mac + '\n' + 'MEM: %3.1f%%'%(100*mininet_host.mem_usage_abs)
                if getattr(widget, 'upper_info', None):
                    canvas.itemconfig(widget.upper_info, text = upper_text)
                else:
                    widget.upper_info = canvas.create_text(self.canvasx(widget.winfo_rootx()+widget.winfo_width()/2, canvas), self.canvasy(widget.winfo_rooty()-5, canvas), text = upper_text, anchor = S)

                if getattr(widget, 'lower_info', None):
                    text = mac
                    canvas.itemconfig(widget.lower_info, text = lower_text)
                else:
                    widget.lower_info = canvas.create_text(self.canvasx(widget.winfo_rootx(), canvas)+widget.winfo_width()/2, self.canvasy(widget.winfo_rooty()+widget.winfo_height()+5, canvas), text = lower_text, anchor = N)

        timer = threading.Timer(1, lambda: self.refreshPhyGui(canvas))
        timer.daemon = True
        timer.start()


    #Graph manipulation

    def updateGraphNode(self, name, options, canvas, canvas_id, old_name = None):
        self._debug("Update node list with node: %s in graph %s"%(name, canvas.unifyType))
        self._debug("Parameter list is %s"% options)

        if canvas.unifyType == 'NF':
            if options['node_type'] == 'VNF':
                self.updateNodeIcon(canvas_id, name, canvas, options)
            if old_name is not None:
                networkx.relabel_nodes(self.nf_g, {old_name:name}, copy = False)
                self._debug("Node with old name %s renamed to %s and parameters before update are %s"%(old_name, name, self.nf_g.node[name]))
            self.nf_g.add_node(name, canvas_id = canvas_id, attr_dict=options)
        elif canvas.unifyType == 'PHY':
            if old_name is not None:
                networkx.relabel_nodes(self.phy_g, {old_name:name}, copy = False)
                self._debug("Node with old name %s renamed to %s and parameters are %s"%(old_name, name, self.phy_g.node[name]))
            self.phy_g.add_node(name, canvas_id = canvas_id, attr_dict=options)
        else:
            raise Exception( "Unknown canvas type: " + canvas.unifyType )

        if old_name:
            w = canvas.nameToWidget[old_name]
            del canvas.nameToWidget[old_name]
            canvas.nameToWidget[name] = w

    def updateGraphEdge(self, source, target, _options, canvas):
        self._debug("Update edge between nodes %s:%s in graph %s"%(source,target, canvas.unifyType))
        options = None
        if _options is not None:
            options = _options.copy()
            if 'dest' in options: del options['dest']
            if 'src' in options: del options['src']
            if 'linkOpts' in options:
                options.update(**options['linkOpts'])
                del options['linkOpts']

        self._debug("Parameter list %s"% options)
        if canvas.unifyType == 'NF':
            self.nf_g.add_edge(source, target, attr_dict=options)
        elif canvas.unifyType == 'PHY':
            if 'weight' not in options: options['weight'] = 1
            self.phy_g.add_edge(source, target, attr_dict=options)
        else:
            raise Exception( "Unknown canvas type: " + canvas.unifyType )

    def removeGraphEdge(self, source, target, canvas):
        self._debug("Remove edge between nodes %s:%s from graph %s"%(source, target, canvas.unifyType))
        if canvas.unifyType == 'NF':
            self.nf_g.remove_edge(source, target)
        elif canvas.unifyType == 'PHY':
            self.phy_g.remove_edge(source, target)
        else:
            raise Exception( "Unknown canvas type: " + canvas.unifyType )

    def removeGraphNode(self, name, canvas):
        self._debug("Remove %s node from graph %s"%(name, canvas.unifyType))
        if canvas.unifyType == 'NF':
            self.nf_g.remove_node(name)
        elif canvas.unifyType == 'PHY':
            self.phy_g.remove_node(name)
        else:
            raise Exception( "Unknown canvas type: " + canvas.unifyType )

    
    def fatal_error_handler(self, _type, _value, _traceback):
        print traceback.print_exception(_type, _value, _traceback)
        error = "%s: %s"%(_type, _value)
        print error
        exit(-1)

    
    def gui_error_handler(self, _type, _value, _traceback):
        print traceback.print_exception(_type, _value, _traceback)
        lines = traceback.format_exception_only(_type, _value)
        msg = '\n'.join(lines)
        tkMessageBox.showerror("Critical exception", msg)
        #TODO: clean and safe quit, kill all daemon thread, etc
        
        os._exit(-1)

    def _gui_warn(self, msg):
        tkMessageBox.showwarning('ESCAPE warning msg', msg)
        self._warning(msg)

def miniEditImages():
    """Create and return images for MiniEdit."""

    # Image data. Git will be unhappy. However, the alternative
    # is to keep track of separate binary files, which is also
    # unappealing.

    def image_resource(img_path):
        return ImageTk.PhotoImage(Image.open(resource_path(img_path)))

    return {
        'Select': BitmapImage( file= resource_path('select') ),
        'Switch': image_resource('switch.png'),
        'LegacySwitch': image_resource('legacy_switch.png'),
        'LegacyRouter': image_resource('legacy_router.png'),
        'Controller': image_resource('pox.png'),
        'Host': image_resource('container_3_small.png'),
        'OldSwitch': image_resource('old_switch.png'),
        'NetLink': image_resource('netlink.png'),
        'Vnf': image_resource('fn.png'),
        'Startpoint': image_resource('entrance.png')
    }


def _main():
    if os.getuid() != 0:
        print "ESCAPE must run as root because of MiniNet"
        return
    logger = logging.getLogger(__name__)

    # POX running thread with init modules
    pox_thread = threading.Thread(target = boot.boot,
                                  name = 'POXThread',
                                  args = (["--handle_signals=False",
                                           "log.level",
                                           "--traffic_steering=DEBUG",
                                           "traffic_steering",
                                           "proto.arp_responder",
                                           "CoreInitListener",
                                           "NetworkManager",
                                           "simple_topology",
                                           "etc_hosts",
                                           ],))
    # Demonize
    pox_thread.daemon = True

    # Set worker thread
    worker = Utils.Worker()
    worker_thread = threading.Thread(target = worker.work,
                                     name = 'WorkerThread')
    worker_thread.daemon = True

    # Start POX and wait for the ready notification from pox.core
    # fired by CoreInitListener module
    CoreInitListener.condition.acquire()
    worker_thread.start()
    pox_thread.start()
    logger.info("Waiting for initialization of pox.core.core")
    CoreInitListener.condition.wait()
    CoreInitListener.condition.release()
    logger.info('Pox core initialized')

    """overwrite loglevel inherited from pox"""
    logging.getLogger().setLevel(logging.DEBUG)

    logger.debug('Remove logHandler defined in pox')
    
    logging.getLogger().removeHandler(pox.core._default_log_handler)

    pox.core.core.callLater(pox.core.core.NetworkManagerMininet.addListeners,
                            pox.core.core.TrafficSteering)
							
    # Init main GUI window
    app = MiniEdit(worker)
    if params.nf_topo:
        app.loadNFTopology(params.nf_topo)
    
    if params.phy_topo:
        app.loadPHYTopology(params.phy_topo)
    # Start GUI event handling loop
    app.mainloop()

params = None

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description = "ESCAPE: Extensible Service \
                                                   ChAin Prototyping \
                                                   Environment using Mininet, \
                                                   Click, NETCONF and POX")

    parser.add_argument('--nf-topo', default = None)
    parser.add_argument('--phy-topo', default = None)

    params = parser.parse_args()

    _main()
