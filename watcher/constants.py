#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>

import os

appname = 'watcher'


def local_socket_address():
    if getattr(local_socket_address, 'ADDRESS', None) is None:
        user = os.environ.get('USER', '')
        if not user:
            user = os.path.basename(os.path.expanduser('~'))
        local_socket_address.ADDRESS = ('\0' + appname + '-daemon').encode('utf-8')
    return local_socket_address.ADDRESS
