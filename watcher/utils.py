#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>

import os
import json


EXCLUDE_VCS_DIRS = frozenset('qt5'.split())
vcs_props = (
    ('git', '.git', os.path.exists),
    # ('mercurial', '.hg', os.path.isdir),
    # ('bzr', '.bzr', os.path.isdir),
)


def generate_directories(path):
    if os.path.isdir(path):
        yield path
    while True:
        if os.path.ismount(path):
            break
        old_path = path
        path = os.path.dirname(path)
        if path == old_path or not path:
            break
        yield path


def deserialize_message(raw):
    return json.loads(raw.decode('utf-8'))


def serialize_message(msg):
    return json.dumps(msg, ensure_ascii=False).encode('utf-8')


def vcs_dir_ok(p):
    for q in EXCLUDE_VCS_DIRS:
        if '/' + q + '/' in p or p.endswith('/' + q):
            return False
    return True


def is_vcs(path):
    for directory in generate_directories(path):
        for vcs, vcs_dir, check in vcs_props:
            repo_dir = os.path.join(directory, vcs_dir)
            if vcs_dir_ok(repo_dir) and check(repo_dir):
                if os.path.isdir(repo_dir) and not os.access(repo_dir, os.X_OK):
                    continue
                return vcs
