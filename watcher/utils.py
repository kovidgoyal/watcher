#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>
from __future__ import print_function, unicode_literals, division

import os
import json
import stat
import subprocess
import sys
from math import log


class String(str):
    pass


def realpath(x):
    return os.path.abspath(os.path.realpath(x))


def print_error(*args, **kw):
    kw['file'] = sys.stderr
    print(*args, **kw)


def ismount(path, stat_func=os.lstat):
    st = stat_func(path)
    if stat.S_ISLNK(st.st_mode):
        return False
    try:
        s1 = stat_func(path)
        s2 = stat_func(os.path.join(path, '..'))
    except EnvironmentError:
        return False  # It doesn't exist -- so not a mount point :-)
    dev1 = s1.st_dev
    dev2 = s2.st_dev
    if dev1 != dev2:
        return True     # path/.. on a different device as path
    ino1 = s1.st_ino
    ino2 = s2.st_ino
    if ino1 == ino2:
        return True     # path/.. is the same i-node as path
    return False


def generate_directories(path):
    cache = {}

    def stat_func(p):
        ans = cache.get(p)
        if ans is None:
            ans = cache[p] = os.lstat(p)
        return ans

    try:
        st = stat_func(path)
    except EnvironmentError:
        pass
    else:
        if stat.S_ISDIR(st.st_mode):
            yield path

        while True:
            if ismount(path, stat_func):
                break
            old_path = path
            path = os.path.dirname(path)
            if not path or path == old_path:
                break
            yield path


def deserialize_message(raw):
    if raw.startswith(b'\x01'):
        return json.loads(raw[1:].decode('utf-8'))
    else:
        raw = raw[1:].decode('utf-8')
        ans = {}
        for line in raw.split('\0'):
            key, val = line.partition(':')[::2]
            ans[key] = val
        return ans


def serialize_message(msg):
    if isinstance(msg, String):
        return msg.encode('utf-8')
    ans = json.dumps(msg, ensure_ascii=False).encode('utf-8')
    ans = b'\x01' + ans
    return ans


def readlines(cmd, cwd=os.getcwd(), decode=True):
    p = subprocess.Popen(cmd, shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=cwd)
    p.stderr.close()
    with p.stdout:
        for line in p.stdout:
            if decode:
                yield line[:-1].decode('utf-8')
            else:
                yield line[:-1]

unit_list = tuple(zip(['', 'k', 'M', 'G', 'T', 'P'], [0, 0, 1, 2, 2, 2]))


def humanize_bytes(num, suffix='B', si_prefix=False, space_before_unit=''):
    '''Return a human friendly byte representation.

    Modified version from http://stackoverflow.com/questions/1094841
    '''
    if num == 0:
        return '0' + suffix
    div = 1000 if si_prefix else 1024
    exponent = min(int(log(num, div)) if num else 0, len(unit_list) - 1)
    quotient = float(num) / div ** exponent
    unit, decimals = unit_list[exponent]
    if unit and not si_prefix:
        unit = unit.upper() + 'i'
    return '{{quotient:.{decimals}f}}{{unit}}{{suffix}}'\
        .format(decimals=decimals)\
        .format(quotient=quotient, unit=unit, suffix=suffix)
