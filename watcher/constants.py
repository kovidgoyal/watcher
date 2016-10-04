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
        local_socket_address.ADDRESS = ('\0' + appname + '-' + user + '-daemon').encode('utf-8')
    return local_socket_address.ADDRESS


def ansi_code(*names):
    fg = '38;5;'
    bg = '48;5;'
    if not hasattr(ansi_code, 'codes'):
        ansi_code.codes = {
            'reset': '0',
            'gray-f': fg + '236',
            'gray-b': bg + '236',
            'yellow-f': fg + '220',
        }
    ans = '%{\x1b['
    if len(names) == 1:
        ans += ansi_code.codes[names[0]] + 'm'
    else:
        for name in names:
            ans += ansi_code.codes[name]
            if name is not names[-1]:
                ans += ';'
        ans += 'm'
    return ans + '%}'
