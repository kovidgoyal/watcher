#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>

import os

from .constants import ansi_code, bg, fg
from .vcs import vcs_data


def vcs_segment(vcs_data, parts):
    if vcs_data['branch']:
        a = parts.append
        a(ansi_code(fg('gray')))
        a('')
        a(ansi_code(bg('gray'), (fg('yellow') if vcs_data['status'] else fg('white'))))
        a('\xa0\xa0')
        a(vcs_data['branch'])
        a('\xa0')


def error_segment(err, parts):
    if err:
        a = parts.append
        a(ansi_code(fg('brightred')))
        a('')
        a(ansi_code(bg('brightred'), fg('white')))
        a('\xa0{}\xa0'.format(err))


def safe_int(x):
    try:
        return int(x)
    except Exception:
        return 0


def prompt_data(which='left', cwd=os.getcwd(), last_exit_code=0, last_pipe_code=0, **k):
    parts = []
    if which == 'right':
        last_exit_code = safe_int(last_exit_code)
        last_pipe_code = safe_int(last_pipe_code)
        err = last_exit_code if last_exit_code != 0 else last_pipe_code if last_pipe_code != 0 else 0
        error_segment(err, parts)
        vcs = vcs_data(cwd)
        vcs_segment(vcs, parts)
        parts.insert(0, '\xa0')
    parts.append(ansi_code('reset'))
    return ''.join(parts)
