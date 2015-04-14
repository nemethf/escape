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

"""
Created on Jul 15, 2014

@author: csoma
"""
import threading

import pox.core


log = None

class CoreInitListener  (object):
  """Wait the UpEvent of the pox.core module
  and send a notification about it."""
  condition = threading.Condition()

  def __init__ (self):
    # Register for core events
    pox.core.core.addListeners(self)

  def _handle_UpEvent (self, event):
    """Handle the UpEvent of the pox.core object"""
    # Notify the waiting threads that the POX (pox.core) is up and running
    CoreInitListener.condition.acquire()
    CoreInitListener.condition.notify()
    CoreInitListener.condition.release()


def launch ():
  global log
  log = pox.core.core.getLogger()
  # Register self into the pox.core object 
  pox.core.core.register(CoreInitListener())
