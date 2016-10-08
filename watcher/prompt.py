#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>

import os

from .constants import ansi_code, bg, fg, hostname, LEFT_DIVIDER, LEFT_END, RIGHT_END, VCS_SYMBOL
from .vcs import vcs_data

CWD_BACKGROUND = 'gray4'
CWD_FOREGROUND = 'white'
CWD_LAST_BG = 'white'
CWD_LAST_FG = 'black'
VCS_BACKGROUND = 'gray2'
VCS_FOREGROUND = USER_FOREGROUND = 'white'
VCS_DIRTY_FOREGROUND = 'yellow'
ERROR_FOREGROUND = 'white'
ERROR_BACKGROUND = 'brightred'
HOSTNAME_BACKGROUND = 'mediumorange'
HOSTNAME_FOREGROUND = 'yellow'
USER_BACKGROUND = 'darkblue'
HELLIPSIS = '⋯'
IGNORE_USER = 'kovid'


def vcs_segment(vcs_data, parts):
    if vcs_data['branch']:
        a = parts.append
        a(ansi_code(fg(VCS_BACKGROUND)))
        a(RIGHT_END)
        a(ansi_code(bg(VCS_BACKGROUND), (fg(VCS_DIRTY_FOREGROUND) if vcs_data['repo_status'] else fg(VCS_FOREGROUND))))
        a('\xa0{}\xa0'.format(VCS_SYMBOL))
        a(vcs_data['branch'])
        a('\xa0')


def error_segment(err, parts):
    if err:
        a = parts.append
        a(ansi_code(fg(ERROR_BACKGROUND)))
        a(RIGHT_END)
        a(ansi_code(bg(ERROR_BACKGROUND), fg(ERROR_FOREGROUND)))
        a('\xa0{}\xa0'.format(err))


def safe_int(x):
    try:
        return int(x)
    except Exception:
        return 0


def right_prompt(cwd, last_exit_code, last_pipe_code):
    parts = []
    last_exit_code = safe_int(last_exit_code)
    last_pipe_code = safe_int(last_pipe_code)
    err = last_exit_code if last_exit_code != 0 else last_pipe_code if last_pipe_code != 0 else 0
    error_segment(err, parts)
    vcs = vcs_data(cwd)
    vcs_segment(vcs, parts)
    parts.insert(0, '\xa0')
    return parts


def hostname_segment(parts, follow_on_bg):
    a = parts.append
    a(ansi_code(fg(HOSTNAME_FOREGROUND), bg(HOSTNAME_BACKGROUND)))
    a('\xa0{}\xa0'.format(hostname()))
    a(ansi_code(fg(HOSTNAME_BACKGROUND), bg(follow_on_bg)))
    a(LEFT_END)


def user_segment(user, parts):
    a = parts.append
    a(ansi_code(fg(USER_FOREGROUND), bg(USER_BACKGROUND)))
    a('\xa0{}\xa0'.format(user))
    a(ansi_code(fg(USER_BACKGROUND), bg(cwd_segment.first_bg)))
    a(LEFT_END)


def cwd_segment(cwd_parts):
    parts = []
    a = parts.append
    a(ansi_code(fg(CWD_FOREGROUND), bg(CWD_BACKGROUND)))
    last = cwd_parts[-1]
    second_last = cwd_parts[-2] if len(cwd_parts) > 1 else None
    for p in cwd_parts:
        if p is last:
            a(ansi_code(fg(CWD_LAST_FG), bg(CWD_LAST_BG)))
        a('\xa0{}\xa0'.format(p))
        if p is last:
            a(ansi_code('reset', fg(CWD_LAST_BG)))
            a(LEFT_END)
        else:
            if p is second_last:
                a(ansi_code(fg(CWD_BACKGROUND), bg(CWD_LAST_BG)))
                a(LEFT_END)
            else:
                a(LEFT_DIVIDER)
        if p is cwd_parts[0]:
            cwd_segment.first_bg = CWD_LAST_BG if p is last else CWD_BACKGROUND
    return parts
cwd_segment.first_bg = CWD_BACKGROUND


def left_prompt(user, cwd, is_ssh, home):
    parts = []
    if cwd == home:
        cwd = '~'
    home = home.rstrip(os.sep) + os.sep
    if cwd.startswith(home):
        cwd = '~' + os.sep + cwd[len(home):]
    cwd_parts = list(filter(None, cwd.split(os.sep)))
    if cwd_parts[0] != '~':
        cwd_parts.insert(0, '/')
    show_user = user.strip() and user != IGNORE_USER
    limit = 3 if is_ssh else 4
    limit -= 1 if show_user else 0
    if len(cwd_parts) > limit:
        cwd_parts = [HELLIPSIS] + cwd_parts[-limit+1:]
    if cwd_parts:
        cwd_parts = cwd_segment(cwd_parts)
    else:
        cwd_segment.first_bg = CWD_BACKGROUND
    if is_ssh:
        hostname_segment(parts, USER_BACKGROUND if show_user else cwd_segment.first_bg)
    if show_user:
        user_segment(user, parts)
    if cwd_parts:
        parts.extend(cwd_parts)
    parts.append('\xa0')

    return parts


def prompt_data(which='left', cwd=os.getcwd(), last_exit_code=0, last_pipe_code=0, is_ssh='0', user='', home='', **k):
    user = user or os.environ.get('USER', os.path.basename(os.path.expanduser('~')))
    if which == 'right':
        parts = right_prompt(cwd, last_exit_code, last_pipe_code)
    else:
        parts = left_prompt(user, cwd, is_ssh == '1', home)
    parts.append(ansi_code('reset'))
    return ''.join(parts)
