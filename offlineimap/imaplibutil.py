# imaplib utilities
# Copyright (C) 2002-2007 John Goerzen
# <jgoerzen@complete.org>
#
#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program; if not, write to the Free Software
#    Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301 USA

import os, re, socket, time, subprocess, sys, threading
from offlineimap.ui import UIBase
from offlineimap.imaplib2 import *

# Import the symbols we need that aren't exported by default
from offlineimap.imaplib2 import IMAP4_PORT, IMAP4_SSL_PORT, InternalDate, Mon2num


class IMAP4_Tunnel(IMAP4):
    """IMAP4 client class over a tunnel

    Instantiate with: IMAP4_Tunnel(tunnelcmd)

    tunnelcmd -- shell command to generate the tunnel.
    The result will be in PREAUTH stage."""

    def __init__(self, tunnelcmd):
        IMAP4.__init__(self, tunnelcmd)

    def open(self, host, port):
        """The tunnelcmd comes in on host!"""
        self.process = subprocess.Popen(host, shell=True, close_fds=True,
                        stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        (self.outfd, self.infd) = (self.process.stdin, self.process.stdout)
        self.read_fd = self.infd.fileno()

    def read(self, size):
        return os.read(self.read_fd, size)

    def readline(self):
        return self.infd.readline()

    def send(self, data):
        self.outfd.write(data)

    def shutdown(self):
        self.infd.close()
        self.outfd.close()
        self.process.wait()
        
class sslwrapper:
    def __init__(self, sslsock):
        self.sslsock = sslsock
        self.readbuf = ''

    def write(self, s):
        return self.sslsock.write(s)

    def _read(self, n):
        return self.sslsock.read(n)

    def read(self, n):
        if len(self.readbuf):
            # Return the stuff in readbuf, even if less than n.
            # It might contain the rest of the line, and if we try to
            # read more, might block waiting for data that is not
            # coming to arrive.
            bytesfrombuf = min(n, len(self.readbuf))
            retval = self.readbuf[:bytesfrombuf]
            self.readbuf = self.readbuf[bytesfrombuf:]
            return retval
        retval = self._read(n)
        if len(retval) > n:
            self.readbuf = retval[n:]
            return retval[:n]
        return retval

    def readline(self):
        retval = ''
        while 1:
            linebuf = self.read(1024)
            nlindex = linebuf.find("\n")
            if nlindex != -1:
                retval += linebuf[:nlindex + 1]
                self.readbuf = linebuf[nlindex + 1:] + self.readbuf
                return retval
            else:
                retval += linebuf

def new_mesg(self, s, tn=None, secs=None):
            if secs is None:
                secs = time.time()
            if tn is None:
                tn = threading.currentThread().getName()
            tm = time.strftime('%M:%S', time.localtime(secs))
            UIBase.getglobalui().debug('imap', '  %s.%02d %s %s' % (tm, (secs*100)%100, tn, s))

class WrappedIMAP4_SSL(IMAP4_SSL):
    def open(self, host=None, port=None):
        IMAP4_SSL.open(self, host, port)
        self.sslobj = sslwrapper(self.sslobj)

    def readline(self):
        return self.sslobj.readline()

mustquote = re.compile(r"[^\w!#$%&'+,.:;<=>?^`|~-]")

def Internaldate2epoch(resp):
    """Convert IMAP4 INTERNALDATE to UT.

    Returns seconds since the epoch.
    """

    mo = InternalDate.match(resp)
    if not mo:
        return None

    mon = Mon2num[mo.group('mon')]
    zonen = mo.group('zonen')

    day = int(mo.group('day'))
    year = int(mo.group('year'))
    hour = int(mo.group('hour'))
    min = int(mo.group('min'))
    sec = int(mo.group('sec'))
    zoneh = int(mo.group('zoneh'))
    zonem = int(mo.group('zonem'))

    # INTERNALDATE timezone must be subtracted to get UT

    zone = (zoneh*60 + zonem)*60
    if zonen == '-':
        zone = -zone

    tt = (year, mon, day, hour, min, sec, -1, -1, -1)

    return time.mktime(tt)
