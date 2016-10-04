#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>

import os

from .constants import ansi_code
from .vcs import vcs_data


def vcs_segment(vcs_data, parts):
    if vcs_data['branch']:
        a = parts.append
        a(ansi_code('gray-f'))
        a('')
        codes = ['gray-b']
        if vcs_data['status']:
            codes.append('yellow-f')
        a(ansi_code(*codes))
        a('\xa0\xa0')
        a(vcs_data['branch'])
        a('\xa0')


def prompt_data(which='left', cwd=os.getcwd(), last_exit_code=0, last_pipe_code=0, **k):
    parts = []
    if which == 'right':
        vcs = vcs_data(cwd)
        vcs_segment(vcs, parts)
    parts.insert(0, '\xa0')
    parts.append(ansi_code('reset'))
    return ''.join(parts)
