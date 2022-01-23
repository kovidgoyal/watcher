#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>


import os
import re

from .utils import generate_directories, realpath, readlines
from .gitstatusd import GSD


# git {{{


gsd = None


def gitcmd(directory, *args):
    return readlines(('git',) + args, directory)


def git_data(directory):
    global gsd
    if gsd is None:
        gsd = GSD()
    data = gsd(directory)
    branch_name = data['branch_name'] or data['HEAD'] or '-no-branch-'
    dirty = (
        data['num_unstaged_changes'] or data['num_staged_changes'] or data['num_untracked_files'] or
        data['num_conflicted_changes'] or data['num_unstaged_deleted_files'] or
        data['num_staged_new_files'] or data['num_staged_deleted_files']
    )
    return branch_name, ('M' if dirty else '')


def git_file_status(directory, subpath):
    try:
        return next(gitcmd(directory, 'status', '--porcelain', '--ignored', '--', subpath))[:2]
    except StopIteration:
        return ''


def git_ignore_modified(path, name):
    return path.endswith('.git') and name == 'index.lock'
# }}}


def is_vcs(path):
    for directory in generate_directories(path):
        for vcs, vcs_dir, check, ignore_event in vcs_props:
            repo_dir = os.path.join(directory, vcs_dir)
            if check(repo_dir):
                if os.path.isdir(repo_dir) and not os.access(repo_dir, os.X_OK):
                    continue
                return vcs, directory, ignore_event
    return None, None, None


vcs_props = (
    ('git', '.git', os.path.exists, git_ignore_modified),
    # ('mercurial', '.hg', os.path.isdir, None),
    # ('bzr', '.bzr', os.path.isdir, None),
)


def escape_branch_name(name):
    # Disallow all characters other than basic alphanumerics. This is done
    # because branch names are displayed in sheels and so can be vulnerable to
    # shell escape based vulnerabilities.
    return re.sub(r'[^a-zA-Z0-9_-]', '_', name)


class VCSWatcher:

    def __init__(self, path, vcs, ignore_event):
        self.path = path
        self.vcs = vcs
        self.ignore_event = ignore_event
        self.branch_name = None
        self.repo_status = None
        self.file_status = {}

    def data(self, subpath=None, both=False):
        self.update(subpath, both)
        return {'branch': self.branch_name, 'repo_status': self.repo_status, 'file_status': self.file_status.get(subpath)}

    def update(self, subpath=None, both=False):
        self.vcs, self.path, self.ignore_event = is_vcs(self.path)
        self.file_status = {}  # All saved file statuses are outdated
        if self.vcs == 'git':
            bn, self.repo_status = git_data(self.path)
            self.branch_name = escape_branch_name(bn)
            if subpath:
                self.file_status[subpath] = git_file_status(self.path, subpath)
        else:
            self.branch_name = self.repo_status = None


watched_trees = {}


def vcs_data(path, subpath=None, both=False):
    path = realpath(path)
    vcs, vcs_dir, ignore_event = is_vcs(path)
    ans = {'branch': None, 'status': None}
    if vcs:
        if subpath and os.path.isabs(subpath):
            subpath = os.path.relpath(subpath, vcs_dir)
        w = watched_trees.get(vcs_dir)
        if w is None:
            watched_trees[path] = w = VCSWatcher(vcs_dir, vcs, ignore_event)
        if w is not None:
            ans = w.data(subpath, both)
    return ans
