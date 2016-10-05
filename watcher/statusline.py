#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>

import sys
import os
import vim
from collections import namedtuple
from functools import wraps, partial
from itertools import count


def debug(*a, **k):
    k['file'] = open('/tmp/log', 'a')
    return print(*a, **k)

# vim bindings {{{
pyeval, python = ('py3eval', 'python3') if sys.version_info.major >= 3 else ('pyeval', 'python')

STATUSLINE = "%%!%s('sys.statusline.render({})')" % pyeval

vim_modes = {
    'n': 'NORMAL',
    'no': 'N·OPER',
    'v': 'VISUAL',
    'V': 'V·LINE',
    '^V': 'V·BLCK',
    's': 'SELECT',
    'S': 'S·LINE',
    '^S': 'S·BLCK',
    'i': 'INSERT',
    'R': 'REPLACE',
    'Rv': 'V·RPLCE',
    'c': 'COMMND',
    'cv': 'VIM EX',
    'ce': 'EX',
    'r': 'PROMPT',
    'rm': 'MORE',
    'r?': 'CONFIRM',
    '!': 'SHELL',
}

mode_translations = {
    chr(ord('V') - 0x40): '^V',
    chr(ord('S') - 0x40): '^S',
}
current_mode = 'nc'
window = window_id = current_buffer = None


def vim_get_func(f, str_returned=False):
    '''Return a vim function binding.'''
    func = vim.bindeval('function("' + f + '")')
    if str_returned:
        @wraps(func)
        def wrapper(*a, **k):
            return func(*a, **k).decode('utf-8', errors='replace')
        return wrapper
    return func
mode = vim_get_func('mode', True)
getpos = vim_get_func('getpos')
virtcol = vim_get_func('virtcol')
fnamemodify = vim_get_func('fnamemodify', True)
expand = vim_get_func('expand', True)
bufnr = vim_get_func('bufnr')
line2byte = vim_get_func('line2byte')
del vim_get_func


def win_idx(window_id):
    ' Install a local statusline in every window, so that we can show correct data when multiple windows are present '
    r = None
    for window in vim.windows:
        try:
            curwindow_id = window.vars['statusline_window_id']
            if r is not None and curwindow_id == window_id:
                raise KeyError
        except KeyError:
            curwindow_id = next(win_idx.window_id)
            window.vars['statusline_window_id'] = curwindow_id
        statusline = STATUSLINE.format(curwindow_id)
        if window.options['statusline'] != statusline:
            window.options['statusline'] = statusline
        if (curwindow_id == window_id) if window_id is not None else (window is vim.current.window):
            r = window, curwindow_id
    return r or (None, None)
win_idx.window_id = count()


def window_cached(func):
    ' Use cached values for func() if called for non-active window '
    cache = {}

    @wraps(func)
    def ret():
        if current_mode == 'nc':
            return cache.get(window_id)
        else:
            r = cache[window_id] = func()
            return r

    return ret


hl_groups = {}


def reset_highlights():
    hl_groups.clear()


def setup():
    sys.statusline = namedtuple('StatusLine', 'render reset_highlights')(statusline, reset_highlights)
    vim.command('augroup statusline')
    vim.command('	autocmd! ColorScheme * :{} sys.statusline.reset_highlights()'.format(python))
    vim.command('	autocmd! VimEnter    * :redrawstatus!')
    vim.command('augroup END')
    vim.command("set statusline=" + STATUSLINE.format(-1))
# }}}


# Left segments {{{

def mode_segment():
    ' Return the current vim mode '
    mode_name = mode_translations.get(current_mode, current_mode)
    ans = vim_modes.get(mode_name)
    if ans is not None:
        return ans


def visual_range():
    '''Return the current visual selection range.

    Returns a value similar to `showcmd`.
    '''
    if current_mode not in ('v', 'V', '^V'):
        return
    pos_start = getpos('v')
    pos_end = getpos('.')
    # Workaround for vim's "excellent" handling of multibyte characters and display widths
    pos_start[2] = virtcol([pos_start[1], pos_start[2], pos_start[3]])
    pos_end[2] = virtcol([pos_end[1], pos_end[2], pos_end[3]])
    visual_start = (int(pos_start[1]), int(pos_start[2]))
    visual_end = (int(pos_end[1]), int(pos_end[2]))
    diff_rows = abs(visual_end[0] - visual_start[0]) + 1
    diff_cols = abs(visual_end[1] - visual_start[1]) + 1
    if current_mode == '^V':
        return '{0} × {1}'.format(diff_rows, diff_cols)
    elif current_mode == 'V' or diff_rows > 1:
        return '{0} rows'.format(diff_rows)
    else:
        return '{0} cols'.format(diff_cols)


def paste_indicator():
    return 'PASTE' if int(vim.eval('&paste')) else None


def readonly_indicator():
    return '' if int(current_buffer.options['readonly']) else None


def file_directory(shorten_user=True, shorten_cwd=True, shorten_home=False):
    '''Return file directory (head component of the file path).

    :param bool shorten_user:
            shorten ``$HOME`` directory to :file:`~/`

    :param bool shorten_cwd:
            shorten current directory to :file:`./`

    :param bool shorten_home:
            shorten all directories in :file:`/home/` to :file:`~user/` instead of :file:`/home/user/`.
    '''
    name = current_buffer.name
    if not name:
        return None
    file_directory = fnamemodify(name, (':~' if shorten_user else '') + (':.' if shorten_cwd else '') + ':h')
    if shorten_home and file_directory.startswith('/home/'):
        file_directory = '~' + file_directory[6:]
    return file_directory + os.sep if file_directory else None


def file_name():
    '''Return file name (tail component of the file path).'''
    name = current_buffer.name
    if not name:
        return None
    file_name = fnamemodify(name, ':~:.:t')
    return file_name


def modified_indicator(text='+'):
    '''Return a file modified indicator. '''
    return '+' if int(current_buffer.options['modified']) else None


def left():
    ans = []
    for seg in left.segments:
        val = seg()
        if val:
            ans.append(val)
    return '\xa0'.join(ans)

left.segments = (
    mode_segment, visual_range, paste_indicator, readonly_indicator,
    file_directory, file_name, modified_indicator)
# }}}

# Right segments {{{


def buf_opt(name):
    return current_buffer.options[name].decode('utf-8', 'replace') or None
file_format = partial(buf_opt, 'fileformat')
file_encoding = partial(buf_opt, 'fileencoding')
file_type = partial(buf_opt, 'filetype')


def line_percent():
    '''Return the cursor position in the file as a percentage.'''
    line_current = window.cursor[0]
    line_last = len(current_buffer)
    percentage = line_current * 100.0 / line_last
    return str(int(round(percentage)))


def line_current():
    '''Return the current cursor line.'''
    return str(window.cursor[0])


def col_current():
    '''Return the current cursor column.  '''
    return str(window.cursor[1] + 1)


@window_cached
def virtcol_current():
    '''Return current visual column with concealed characters ingored'''
    col = virtcol('.')
    return str(col)


def right():
    ans = []
    for seg in right.segments:
        val = seg()
        if val:
            ans.append(val)
    return '\xa0'.join(ans)
right.segments = (file_format, file_encoding, file_type, line_percent, line_current, virtcol_current)

# }}}


def statusline(wid):
    ' The function responsible for rendering the statusline '
    global current_mode, window, window_id, current_buffer
    window, window_id = win_idx(None if wid == -1 else wid)
    try:
        if not window:
            return 'No window for window_id: {!r}'.format(window_id)
        current_buffer = window.buffer
        current_mode = mode(1) if window is vim.current.window else 'nc'
        ans = left()
        ans += '%='  # left/right separator
        ans += right()
        return ans
    finally:
        current_mode = 'nc'
        window = window_id = current_buffer = None  # Prevent leaks
