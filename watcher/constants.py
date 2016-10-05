#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>
from __future__ import unicode_literals

import os

appname = 'watcher'
LEFT_DIVIDER = ''
RIGHT_DIVIDER = ''
LEFT_END = ''
RIGHT_END = ''
VCS_SYMBOL = ''
CLOCK = "\U0001F552"


def local_socket_address():
    if getattr(local_socket_address, 'ADDRESS', None) is None:
        user = os.environ.get('USER', '')
        if not user:
            user = os.path.basename(os.path.expanduser('~'))
        local_socket_address.ADDRESS = ('\0' + appname + '-' + user + '-daemon').encode('utf-8')
    return local_socket_address.ADDRESS


def hostname():
    ans = getattr(hostname, 'ans', None)
    if ans is None:
        try:
            with open('/etc/hostname', 'rb') as f:
                ans = hostname.ans = f.read().decode('utf-8').strip()
        except Exception:
            ans = hostname.ans = 'unknown'
    return ans


def ansi_codes():
    if not hasattr(ansi_codes, 'codes'):
        ansi_codes.codes = {
            "black": 16,
            "white": 7,
            "brightwhite": 231,

            'gray': 236,
            'yellow': 220,

            "darkestgreen": 22,
            "darkgreen": 28,
            "mediumgreen": 70,
            "brightgreen": 148,

            "darkestcyan": 23,
            "darkcyan": 74,
            "mediumcyan": 117,
            "brightcyan": 159,

            "darkestblue": 24,
            "darkblue": 31,

            "darkestred": 52,
            "darkred": 88,
            "mediumred": 124,
            "brightred": 160,
            "brightestred": 196,

            "darkestpurple": 55,
            "mediumpurple": 98,
            "brightpurple": 189,

            "darkorange": 94,
            "mediumorange": 166,
            "brightorange": 208,
            "brightestorange": 214,

            "gray0": 233,
            "gray1": 235,
            "gray2": 236,
            "gray3": 239,
            "gray4": 240,
            "gray5": 241,
            "gray6": 244,
            "gray7": 245,
            "gray8": 247,
            "gray9": 250,
            "gray10": 252,

            "lightyellowgreen": 106,
            "gold3": 178,
            "orangered": 202,

            "steelblue": 67,
            "darkorange3": 166,
            "skyblue1": 117,
            "khaki1": 228
        }
    return ansi_codes.codes


def fg(name):
    return '38;5;{};'.format(ansi_codes()[name])


def bg(name):
    return '48;5;{};'.format(ansi_codes()[name])


def ansi_code(*args):
    args = ('33;0;' if x == 'reset' else x for x in args)
    ans = '%{\x1b[' + ''.join(args)
    ans = ans.rstrip(';') + 'm%}'
    return ans
