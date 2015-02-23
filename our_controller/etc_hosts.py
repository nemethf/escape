# Copyright (c) 2014 Felician Nemeth
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
# along with POX. If not, see <http://www.gnu.org/licenses/>.

"""
Maintains a host list at the end of /etc/hosts

Ideally, we could use mDNS, but mininet doesn't work with libnss/avahi
"""

import os
from pox.core import core

log = core.getLogger()


class EtcHosts(object):
    def __init__(self):
        core.listen_to_dependencies(self)

    def _handle_SimpleTopology_RecentlyChanged(self, event):
        host_addresses = ''
        for node_name, ip_addr in core.SimpleTopology.get_node_ip_pairs():
            if not ip_addr:
                continue
            host_addresses += "%s\t%s\n" % (ip_addr, node_name)

        start_str = "# begin: ESCAPE\n"
        end_str = "# end: ESCAPE\n"
        tempfile = '/etc/hosts.escape'
        hostfile = '/etc/hosts'
        state = 'before'
        with open(tempfile, "wt") as fout:
            with open(hostfile, "rt") as fin:
                for line in fin:
                    if state == 'before':
                        fout.write(line)
                        if line == start_str:
                            fout.write(host_addresses)
                            fout.write(end_str)
                            state = 'in_between'
                    elif state == 'in_between':
                        if line == end_str:
                            state = 'after'
                    elif state == 'after':
                        fout.write(line)
            if state == 'before':
                fout.write(start_str)
                fout.write(host_addresses)
                fout.write(end_str)

        os.rename(tempfile, hostfile)


def launch():
    core.register(EtcHosts())
