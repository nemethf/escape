# Copyright (c) 2014 Attila Csoma
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

'''
Created on Jul 18, 2014

@author: csoma
'''
import Queue
import logging
import re
import sys


class Store:
    """Dummy class with __dict__ attribute, to store arbitrary value"""
    pass


class LoggerHelper(object):

    def _getLogger(self):
        try:
            return self.logger
        except AttributeError:
            self.logger = logging.getLogger(self.__class__.__name__)
            return self.logger

    def _debug(self, msg, *args, **kwargs):
        self._getLogger().debug(msg, *args, **kwargs)

    def _info(self, msg, *args, **kwargs):
        self._getLogger().info(msg, *args, **kwargs)

    def _critical(self, msg, *args, **kwargs):
        self._getLogger().critical(msg, *args, **kwargs)

    def _fatal(self, msg, *args, **kwargs):
        self._getLogger().fatal(msg, *args, **kwargs)

    def _error(self, msg, *args, **kwargs):
        self._getLogger().error(msg, *args, **kwargs)

    def _warn(self, msg, *args, **kwargs):
        self._getLogger().warn(msg, *args, **kwargs)

    def _warning(self, msg, *args, **kwargs):
        self._getLogger().warning(msg, *args, **kwargs)

    def _exception(self, msg, *args, **kwargs):
        self._getLogger().exception(msg, *args, **kwargs)

class Worker(LoggerHelper):

    def __init__(self):
        self.jobs = Queue.Queue()
        self.error_handler = None

    def work(self):
        while True:
            (func, arg, kw) = self.jobs.get(block = True)
            self._debug('Run %s func with %s %s'%(func, arg, kw))
            try:
                func(*arg, **kw)
            except:
                if self.error_handler:
                    self.error_handler(sys.exc_type, sys.exc_value,
                                       sys.exc_traceback)
                else:
                    raise

    def schedule(self, func, *arg, **kw):
        self._debug('schedule %s with parameters %s %s'%(func, arg, kw))
        self.jobs.put((func, arg, kw), block = False)

class GenericEventNotifyer(object):

    L = '_handle_'
    F = '_fire_'

    def __init__(self):
        self.event_listeners = dict()
        self.regex = re.compile(GenericEventNotifyer.L + '*')

    def register_listener(self, obj, *args, **kwargs):
        registered = list()
        methods = filter(self.regex.match, dir(obj))
        for method in methods:
            event = method[len(GenericEventNotifyer.L):]
            callback = getattr(obj, method)
            self.register_listener_function(event, callback,
                                            *args, **kwargs)
            registered.append(event)

        return registered



    def register_listener_function(self, event, callback, *args, **kwargs):
        fire_event = getattr(self, GenericEventNotifyer.F + event, None)
        if not fire_event:
            return
        try:
            listeners = self.event_listeners[event]
        except KeyError:
            listeners = list()
            self.event_listeners[event] = listeners
        listeners.append((callback, args, kwargs))



    def fire(self, event_name, event):
        listeners = None
        try:
            listeners = self.event_listeners[event_name]
        except KeyError:
            #0 registered listener to this event
            return

        for listener, args, kwargs in listeners:
            listener(event, *args, **kwargs)

