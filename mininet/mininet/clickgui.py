"""
Click GUI creation (cleanup is the same as for xterms).
Utility functions to run a click gui (connected via socat(1)) on each host.

Requires socat(1) and clicky.
"""
from pkg_resources import resource_filename
from term import *

from log import error
from util import quietRun, errRun

def defaultCcssFile():
    return resource_filename("mininet", 'clicky.ccss')

def makeClicky( node, title='Node', clickgui='clicky',
                ccssfile=None, display=None, control_port=None, **kw ):
    """Create an X11 tunnel to the node and start up a clicky GUI.
       node: Node object
       title: base title
       clickgui: 'clicky'
       returns: two Popen objects, tunnel and clicky"""
    title += ': ' + node.name
    if not ccssfile:
        ccssfile = defaultCcssFile()
    if not node.inNamespace:
        title += ' (root)'
    if not control_port:
        control_port = '8001'
    sock = node.IP() + ":" + control_port
    cmds = {
        'clicky': [ 'clicky', '-s', ccssfile, '-p' , sock]
    }
    if clickgui not in cmds:
        error( 'invalid command : %s' % clickgui )
        return
    display, tunnel = tunnelX11( node, display )
    if display is None:
        return []
    clickgui = node.popen( cmds[ clickgui ] )
    return [ tunnel, clickgui ] if tunnel else [ clickgui ]

def makeClickys( nodes, title='Node', clickgui='clicky', ccssfile=None ):
    """Create clicky GUIs.
       nodes: list of Node objects
       title: base title for each
       returns: list of created tunnel/clicky processes"""
    clickys = []
    for node in nodes:
        clickys += makeClicky( node, title, clickgui, ccssfile)
    return clickys
