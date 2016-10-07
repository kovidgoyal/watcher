#!/usr/bin/env python
# vim:fileencoding=utf-8:nospell
# License: GPL v3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>
from __future__ import division, unicode_literals, print_function

import sys
import os
import vim
from collections import namedtuple
from itertools import count

from .constants import LEFT_END, LEFT_DIVIDER, RIGHT_END, RIGHT_DIVIDER, VCS_SYMBOL, LOCK
from .client import connect, send_msg, recv_msg
from .utils import realpath


def debug(*a, **k):
    k['file'] = open('/tmp/log', 'a')
    return print(*a, **k)

# vim bindings {{{
pyeval, python = ('py3eval', 'python3') if sys.version_info.major >= 3 else ('pyeval', 'python')

STATUSLINE = "%%!%s('sys.statusline.render({})')" % pyeval

current_mode = 'nc'


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
        vim.command('''
function g:Get_statusline_data(winnr)
    let cbufnr = winbufnr(a:winnr)
    let m = 'nc'
    let vstart = ''
    let vend = ''
    if a:winnr == winnr()
        let m = mode(1)
        if m == 'v' || m == 'V' || m == '\026'
            let vstart = getpos('v')
            let vend = getpos('.')
            let vstart[2] = virtcol([vstart[1], vstart[2], vstart[3]])
            let vend[2] = virtcol([vend[1], vend[2], vend[3]])
        endif
    endif
    let name = bufname(cbufnr)
    let file_directory = name != '' ? fnamemodify(name, ':~:.:h') : ''
    let file_name = name != '' ? fnamemodify(name, ':~:.:t') : ''
    let ans = {'mode':m, 'bufname':name, 'file_directory':file_directory, 'file_name':file_name, \
        'readonly':getbufvar(cbufnr, "&readonly"), 'modified':getbufvar(cbufnr, "&modified"), \
        'buftype':getbufvar(cbufnr, "&buftype"), 'fileformat':getbufvar(cbufnr, '&fileformat'), \
        'fileencoding':getbufvar(cbufnr, '&fileencoding'), 'filetype':getbufvar(cbufnr, '&filetype'), \
        'vstart':vstart, 'vend':vend \
    }
    return ans
endfunction
''')

        sys.statusline = namedtuple('StatusLine', 'render reset_highlights')(statusline, reset_highlights)
        vim.command('augroup statusline')
        vim.command('	autocmd! ColorScheme * :{} sys.statusline.reset_highlights()'.format(python))
        vim.command('	autocmd! VimEnter    * :redrawstatus!')
        vim.command('augroup END')
        vim.command("set statusline=" + STATUSLINE.format(-1))
# }}}


def escape(text):
    return text.replace(' ', '\xa0').replace('%', '%%')


def segment(fg=None, bg=None, bold=False, soft_divider=False, hard_divider=False, escape=escape):
    def decorator(func):
        func.fg, func.bg, func.bold = fg, bg, bold
        func.soft_divider = soft_divider
        func.hard_divider = hard_divider
        func.escape = escape
        return func
    return decorator


def render_segments(segments):
    for seg in segments:
        val = seg()
        if val:
            yield val, seg


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
    pos_start, pos_end = statusline.data['vstart'], statusline.data['vend']
    if not pos_start:
        return
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


@segment(hard_divider=True, bg='gray2')
def branch():
    if fetch_vcs_data.branch:
        branch.fg = 'brightyellow' if fetch_vcs_data.repo_status else 'white'
        return VCS_SYMBOL + '\xa0' + fetch_vcs_data.branch


@segment(fg='brightestred', bg='gray3')
def readonly_indicator():
    return LOCK + '\xa0' if int(statusline.data['readonly']) else None


@segment(fg='gray8', bg=readonly_indicator.bg)
def file_directory():
    '''Return file directory (head component of the file path).  '''
    name = statusline.data['bufname']
    if not name:
        return None
    file_directory = statusline.data['file_directory']
    if file_directory.startswith('/home/'):
        file_directory = '~' + file_directory[6:]
    return file_directory + os.sep if file_directory else None


@segment(fg='white', bg=file_directory.bg, bold=True)
def file_name():
    '''Return file name (tail component of the file path).'''
    name = statusline.data['bufname']
    if not name:
        return None
    ans = statusline.data['file_name']
    is_modified = int(statusline.data['modified'])
    file_name.fg = 'brightyellow' if is_modified else 'white'
    return ans


@segment(bg=file_name.bg)
def file_status():
    d = fetch_vcs_data.file_status
    if d:
        color = 'white'
        if 'M' in d:
            color = 'brightestorange' if d == ' M' else 'brightgreen'
        elif 'A' in d:
            color = 'brightgreen'
        elif 'D' in d:
            color = 'brightestred'
        elif '??' == d:
            color = 'brightred'
        file_status.fg = color
        return '\xa0' + d.rstrip()


def fetch_vcs_data():
    name = statusline.data['bufname']
    fetch_vcs_data.repo_status = fetch_vcs_data.file_status = fetch_vcs_data.branch = None
    if name and not statusline.data['buftype']:
        s = connect()
        path = realpath(name)
        both = not os.path.isdir(path)
        subpath = None
        if both:
            subpath, path = path, os.path.dirname(path)
        if not subpath.startswith('.git/'):
            send_msg(s, {'q': 'vcs', 'path': path, 'subpath': subpath, 'both': both})
            ans = recv_msg(s)
            if ans['ok']:
                fetch_vcs_data.repo_status = ans.get('repo_status')
                fetch_vcs_data.branch = ans.get('branch')
                fetch_vcs_data.file_status = ans.get('file_status')


def left():
    ans = []
    segments = tuple(render_segments(left.segments))
    for i, (val, segment) in enumerate(segments):
        if i == 0:
            val = '\xa0' + val
        ans.append(colored(segment.escape(val), fg=segment.fg, bg=segment.bg, bold=segment.bold))
        add_hard_divider = segment.hard_divider or i == len(segments) - 1 or segments[i + 1][1].bg != segment.bg
        if add_hard_divider:
            ans.append(colored('\xa0', fg=segment.fg, bg=segment.bg, bold=segment.bold))
            ans.append(colored(LEFT_END + '\xa0', fg=segment.bg, bg=None if i == len(segments) - 1 else segments[i + 1][1].bg))
        else:
            if segment.soft_divider:
                ans.append(colored('\xa0' + LEFT_DIVIDER + '\xa0', fg=segment.fg, bg=segment.bg))
    return ''.join(ans)

left.segments = (
    mode_segment, visual_range, branch,
    readonly_indicator, file_directory, file_name, file_status)
# }}}

# Right segments {{{


def file_data(name):
    @segment(fg='gray8', soft_divider=True)
    def func():
        return statusline.data[name] or None
    func.__name__ = str(name)
    return func

file_format = file_data('fileformat')
file_encoding = file_data('fileencoding')
file_type = file_data('filetype')


@segment(fg='white', bg='gray2', escape=lambda x: x)
def line_percent():
    '''Return the cursor position in the file as a percentage.'''
    return '%p%%'


@segment(bg='white', fg='black', bold=True, escape=lambda x: x)
def line_current():
    '''Return the current cursor line.'''
    return '\xa0%l'


@segment(bg=line_current.bg, fg='gray4', escape=lambda x: x)
def virtcol_current():
    '''Return current visual column with concealed characters ingored'''
    return ':%v'


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
        ans.append(colored(segment.escape(val), fg=segment.fg, bg=segment.bg, bold=segment.bold))

    return ''.join(ans)
right.segments = (file_format, file_encoding, file_type, line_percent, line_current, virtcol_current)

# }}}


def statusline(wid):
    ' The function responsible for rendering the statusline '
    global current_mode
    window, window_id = win_idx(None if wid == -1 else wid)
    try:
        if not window:
            return 'No window for window_id: {!r}'.format(window_id)
        current_data = statusline.data = vim.eval('g:Get_statusline_data({})'.format(window.number))
        current_mode = current_data['mode']
        fetch_vcs_data()
        ans = left()
        ans += '%='  # left/right separator
        ans += right()
        return ans
    finally:
        current_mode = 'nc'
