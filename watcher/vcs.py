#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>


import os
import re

from .inotify import add_tree_watch
from .utils import generate_directories, realpath, readlines

EXCLUDE_VCS_DIRS = frozenset('qt5'.split())


# git {{{
def git_directory(directory):
    path = os.path.join(directory, '.git')
    try:
        with open(path, 'rb') as f:
            raw = f.read().partition(b':')[2].strip().decode('utf-8')
            return os.path.abspath(os.path.join(directory, raw))
    except EnvironmentError:
        return path


def git_branch_name(base_dir):
    head = os.path.join(git_directory(base_dir), 'HEAD')
    try:
        with open(head, 'rb') as f:
            raw = f.read().decode('utf-8')
    except (EnvironmentError, ValueError):
        return None
    m = git_branch_name.ref_pat.match(raw)
    if m is not None:
        return m.group(1)
    return raw[:7]
git_branch_name.ref_pat = re.compile(r'ref:\s*refs/heads/(.+)')


def gitcmd(directory, *args):
    return readlines(('git',) + args, directory)


def git_repo_status(directory):
    wt_column = ' '
    index_column = ' '
    untracked_column = ' '
    for line in gitcmd(directory, 'status', '--porcelain'):
        if line[0] == '?':
            untracked_column = 'U'
            continue
        elif line[0] == '!':
            continue

        if line[0] != ' ':
            index_column = 'I'

        if line[1] != ' ':
            wt_column = 'D'

    r = wt_column + index_column + untracked_column
    return r if r.strip() else ''


def git_file_status(directory, subpath):
    try:
        return next(gitcmd(directory, 'status', '--porcelain', '--ignored', '--', subpath))[:2]
    except StopIteration:
        return ''


def git_status(directory, subpath, both=False):
    if both:
        return git_repo_status(directory), git_file_status(directory, subpath)
    if subpath:
        return None, git_file_status(directory, subpath)
    return git_repo_status(directory), None


def git_ignore_modified(path, name):
    return path.endswith('.git') and name == 'index.lock'
# }}}


def vcs_dir_ok(p):
    for q in EXCLUDE_VCS_DIRS:
        if '/' + q + '/' in p or p.endswith('/' + q):
            return False
    return True


def is_vcs(path):
    for directory in generate_directories(path):
        for vcs, vcs_dir, check, ignore_event in vcs_props:
            repo_dir = os.path.join(directory, vcs_dir)
            if vcs_dir_ok(repo_dir) and check(repo_dir):
                if os.path.isdir(repo_dir) and not os.access(repo_dir, os.X_OK):
                    continue
                return vcs, directory, ignore_event
    return None, None, None

vcs_props = (
    ('git', '.git', os.path.exists, git_ignore_modified),
    # ('mercurial', '.hg', os.path.isdir, None),
    # ('bzr', '.bzr', os.path.isdir, None),
)


class VCSWatcher:

    def __init__(self, path, vcs, ignore_event):
        self.path = path
        self.vcs = vcs
        self.ignore_event = ignore_event
        self.branch_name = None
        self.repo_status = None
        self.file_status = {}

    @property
    def tree_watcher(self):
        return add_tree_watch(self.path, self.ignore_event)

    def data(self, subpath=None, both=False):
        if self.branch_name is None or self.repo_status is None or (subpath and subpath not in self.file_status) or \
                self.tree_watcher.was_modified_since_last_call(self.ignore_event):
            self.update(subpath, both)
        return {'branch': self.branch_name, 'repo_status': self.repo_status, 'file_status': self.file_status.get(subpath)}

    def update(self, subpath=None, both=False):
        self.vcs, self.path, self.ignore_event = is_vcs(self.path)
        self.file_status = {}  # All saved file statuses are outdated
        if self.vcs == 'git':
            self.branch_name = git_branch_name(self.path)
            self.repo_status, self.file_status[subpath] = git_status(self.path, subpath, both)
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
