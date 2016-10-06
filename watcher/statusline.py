#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>

import sys
import os
import vim
from collections import namedtuple
from functools import wraps
from itertools import count

from .constants import LEFT_END, LEFT_DIVIDER, RIGHT_END, RIGHT_DIVIDER


def debug(*a, **k):
    k['file'] = open('/tmp/log', 'a')
    return print(*a, **k)

# vim bindings {{{
pyeval, python = ('py3eval', 'python3') if sys.version_info.major >= 3 else ('pyeval', 'python')

STATUSLINE = "%%!%s('sys.statusline.render({})')" % pyeval

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


def highlight(fg=None, bg=None, bold=False):
    '''Highlight a segment. Automatically creates the highlighting group, on-demand. '''
    # We don't need to explicitly reset attributes in vim, so skip those calls
    if not bold and not bg and not fg:
        return ''

    if not (fg, bg, bold) in hl_groups:
        hl_group = {
            'ctermfg': 'NONE',
            'guifg': 'NONE',
            'ctermbg': 'NONE',
            'guibg': 'NONE',
            'attr': ['NONE'],
        }
        if fg:
            hl_group['ctermfg'] = fg[0]
            hl_group['guifg'] = fg[1]
        if bg:
            hl_group['ctermbg'] = bg[0]
            hl_group['guibg'] = bg[1]
        if bold:
            hl_group['attr'] = ['bold']
        hl_group['name'] = 'Sl_' + \
            str(hl_group['ctermfg']) + '_' + \
            str(hl_group['guifg']) + '_' + \
            str(hl_group['ctermbg']) + '_' + \
            str(hl_group['guibg']) + '_' + \
            ''.join(hl_group['attr'])
        hl_groups[(fg, bg, bold)] = hl_group
        vim.command('hi {group} ctermfg={ctermfg} guifg={guifg} guibg={guibg} ctermbg={ctermbg} cterm={attr} gui={attr}'.format(
            group=hl_group['name'],
            ctermfg=hl_group['ctermfg'],
            guifg=hl_group['guifg'],
            ctermbg=hl_group['ctermbg'],
            guibg=hl_group['guibg'],
            attr=','.join(hl_group['attr']),
        ))
    return '%#' + hl_groups[(fg, bg, bold)]['name'] + '#'


nc_color_translations = {
    "brightyellow": "darkorange",
    "brightestred": "darkred",
    "gray0": "gray0",
    "gray1": "gray0",
    "gray2": "gray0",
    "gray3": "gray1",
    "gray4": "gray1",
    "gray5": "gray1",
    "gray6": "gray1",
    "gray7": "gray4",
    "gray8": "gray4",
    "gray9": "gray4",
    "gray10": "gray5",
    "white": "gray6",
}

mode_colors = {
    'n': {'fg': 'darkestgreen', 'bg': 'brightgreen'},
    'i': {'fg': 'white', 'bg': 'darkestcyan'},
    'v': {"fg": "darkorange", "bg": "brightestorange"},
    'V': {"fg": "darkorange", "bg": "brightestorange"},
    '^V': {"fg": "darkorange", "bg": "brightestorange"},
    'R': {"fg": "white", "bg": "brightred"},
}

vim_gui_color_map = {
    # Map color names used in this file to names vim recognizes
    'brightyellow': 'yellow1',

    'brightestred': 'red1',
    'brightred': 'red2',
    'darkred': 'red3',

    'darkorange': 'orangered1',
    'brightestorange': 'goldenrod',

    'brightgreen': 'olivedrab1',
    'darkestgreen': 'green4',

    'darkestcyan': 'cyan4',
    'gray0': 'gray10',
    'gray1': 'gray18',
    'gray2': 'gray26',
    'gray3': 'gray34',
    'gray4': 'gray43',
    'gray5': 'gray49',
    'gray6': 'gray55',
    'gray7': 'gray63',
    'gray8': 'gray66',
    'gray9': 'gray73',
    'gray10': 'gray80',
}

vim_tui_color_map = {
    # Map color names used in this file to names vim recognizes
    'brightyellow': '226',

    'brightestred': '196',
    'brightred': '160',
    'darkred': '88',

    'darkorange': '202',
    'brightestorange': '227',

    'brightgreen': '191',
    'darkestgreen': '28',

    'darkestcyan': '36',

    'gray0': '234',
    'gray1': '236',
    'gray2': '238',
    'gray3': '240',
    'gray4': '242',
    'gray5': '244',
    'gray6': '246',
    'gray7': '248',
    'gray8': '250',
    'gray9': '252',
}


def color(name):
    if name is None:
        return None
    if current_mode == 'nc':
        name = nc_color_translations.get(name, name)
    return vim_tui_color_map.get(name, name), vim_gui_color_map.get(name, name)


def colored(text, fg=None, bg=None, bold=False):
    fg, bg = map(color, (fg, bg))
    return highlight(fg, bg, bold) + text


def safe_int(x):
    try:
        return int(x)
    except Exception:
        return 0


def setup():
    if safe_int(vim.eval('has("gui_running")')) or safe_int(vim.eval('&t_Co')) >= 256:
        sys.statusline = namedtuple('StatusLine', 'render reset_highlights')(statusline, reset_highlights)
        vim.command('augroup statusline')
        vim.command('	autocmd! ColorScheme * :{} sys.statusline.reset_highlights()'.format(python))
        vim.command('	autocmd! VimEnter    * :redrawstatus!')
        vim.command('augroup END')
        vim.command("set statusline=" + STATUSLINE.format(-1))
# }}}


def segment(fg=None, bg=None, bold=False, soft_divider=False, hard_divider=False):
    def decorator(func):
        func.fg, func.bg, func.bold = fg, bg, bold
        func.soft_divider = soft_divider
        func.hard_divider = hard_divider
        return func
    return decorator


def render_segments(segments):
    for seg in segments:
        val = seg()
        if val:
            yield val, seg


def escape(text):
    return text.replace(' ', '\xa0').replace('%', '%%')


# Left segments {{{

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


@segment(bold=True, hard_divider=True)
def mode_segment():
    ' Return the current vim mode '
    mode_name = mode_translations.get(current_mode, current_mode)
    ans = vim_modes.get(mode_name)
    if ans is not None:
        p = 'PASTE' if int(vim.eval('&paste')) else None
        if p:
            ans += ' [paste]'
        q = mode_name if mode_name in mode_colors else mode_name[0]
        cols = mode_colors.get(q, {'fg': 'white', 'bg': 'black'})
        mode_segment.fg, mode_segment.bg = cols['fg'], cols['bg']
        return ans


@segment(fg='brightestorange', bg='darkorange')
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


@segment(fg='brightestred', bg='gray4')
def readonly_indicator():
    return '\xa0' if int(current_buffer.options['readonly']) else None


@segment(fg='gray8', bg=readonly_indicator.bg)
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


@segment(fg='white', bg=file_directory.bg)
def file_name():
    '''Return file name (tail component of the file path).'''
    name = current_buffer.name
    if not name:
        return None
    ans = fnamemodify(name, ':~:.:t')
    is_modified = int(current_buffer.options['modified'])
    file_name.fg = 'brightyellow' if is_modified else 'white'
    return ans


def left():
    ans = []
    segments = tuple(render_segments(left.segments))
    for i, (val, segment) in enumerate(segments):
        if i == 0:
            val = '\xa0' + val
        ans.append(colored(escape(val), fg=segment.fg, bg=segment.bg, bold=segment.bold))
        add_hard_divider = segment.hard_divider or i == len(segments) - 1 or segments[i + 1][1].bg != segment.bg
        if add_hard_divider:
            ans.append(colored('\xa0', fg=segment.fg, bg=segment.bg, bold=segment.bold))
            ans.append(colored(LEFT_END + '\xa0', fg=segment.bg, bg=None if i == len(segments) - 1 else segments[i + 1][1].bg))
        else:
            if segment.soft_divider:
                ans.append(colored('\xa0' + LEFT_DIVIDER + '\xa0', fg=segment.fg, bg=segment.bg))
    return ''.join(ans)

left.segments = (
    mode_segment, visual_range, readonly_indicator,
    file_directory, file_name)
# }}}

# Right segments {{{


def file_data(name):
    @segment(fg='gray8', soft_divider=True)
    def func():
        return current_buffer.options[name].decode('utf-8', 'replace') or None
    func.__name__ = name
    return func

file_format = file_data('fileformat')
file_encoding = file_data('fileencoding')
file_type = file_data('filetype')


@segment(fg='white', bg='gray2')
def line_percent():
    '''Return the cursor position in the file as a percentage.'''
    line_current = window.cursor[0]
    line_last = len(current_buffer)
    percentage = line_current * 100.0 / line_last
    return str(int(round(percentage))) + '%'


@segment(bg='white', fg='black', bold=True)
def line_current():
    '''Return the current cursor line.'''
    return '\xa0' + str(window.cursor[0])


@segment()
def col_current():
    '''Return the current cursor column.  '''
    return str(window.cursor[1] + 1)


@window_cached
@segment(bg=line_current.bg, fg='gray4')
def virtcol_current():
    '''Return current visual column with concealed characters ingored'''
    col = virtcol('.')
    return ':' + str(col)


def right():
    ans = []
    segments = tuple(render_segments(right.segments))
    for i, (val, segment) in enumerate(segments):
        add_hard_divider = segment.hard_divider or i == 0 or segments[i - 1][1].bg != segment.bg
        if add_hard_divider:
            ans.append(colored('\xa0'))
            if segment.bg:
                ans.append(colored(RIGHT_END, fg=segment.bg, bg=None if i == 0 else segments[i - 1][1].bg))
            ans.append(colored('\xa0', fg=segment.fg, bg=segment.bg, bold=segment.bold))
        else:
            if segment.soft_divider:
                ans.append(colored('\xa0' + RIGHT_DIVIDER + '\xa0', fg=segment.fg, bg=segment.bg))
        if i == len(segments) - 1:
            val += '\xa0'
        ans.append(colored(escape(val), fg=segment.fg, bg=segment.bg, bold=segment.bold))

    return ''.join(ans)
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
