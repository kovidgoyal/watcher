#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>

import os
import errno
import sys
import struct
import ctypes
from collections import namedtuple
from time import monotonic


class DirTooLarge(ValueError):

    def __init__(self, bdir):
        ValueError.__init__(self, 'The directory {0} is too large to monitor. Try increasing the value in /proc/sys/fs/inotify/max_user_watches'.format(bdir))


INotify = namedtuple('INotify', 'init1 add_watch rm_watch')

# See <sys/inotify.h> for the flags defined below

# Supported events suitable for MASK parameter of INOTIFY_ADD_WATCH.
ACCESS = 0x00000001         # File was accessed.
MODIFY = 0x00000002         # File was modified.
ATTRIB = 0x00000004         # Metadata changed.
CLOSE_WRITE = 0x00000008    # Writtable file was closed.
CLOSE_NOWRITE = 0x00000010  # Unwrittable file closed.
OPEN = 0x00000020           # File was opened.
MOVED_FROM = 0x00000040     # File was moved from X.
MOVED_TO = 0x00000080       # File was moved to Y.
CREATE = 0x00000100         # Subfile was created.
DELETE = 0x00000200         # Subfile was deleted.
DELETE_SELF = 0x00000400    # Self was deleted.
MOVE_SELF = 0x00000800      # Self was moved.

# Events sent by the kernel.
UNMOUNT = 0x00002000     # Backing fs was unmounted.
Q_OVERFLOW = 0x00004000  # Event queued overflowed.
IGNORED = 0x00008000     # File was ignored.

# Helper events.
CLOSE = (CLOSE_WRITE | CLOSE_NOWRITE)  # Close.
MOVE = (MOVED_FROM | MOVED_TO)         # Moves.

# Special flags.
ONLYDIR = 0x01000000      # Only watch the path if it is a directory.
DONT_FOLLOW = 0x02000000  # Do not follow a sym link.
EXCL_UNLINK = 0x04000000  # Exclude events on unlinked objects.
MASK_ADD = 0x20000000     # Add to the mask of an already existing watch.
ISDIR = 0x40000000        # Event occurred against dir.
ONESHOT = 0x80000000      # Only send event once.

# All events which a program can wait on.
ALL_EVENTS = (ACCESS | MODIFY | ATTRIB | CLOSE_WRITE | CLOSE_NOWRITE |
              OPEN | MOVED_FROM | MOVED_TO | CREATE | DELETE |
              DELETE_SELF | MOVE_SELF)


def load_inotify():  # {{{
    ''' Initialize the inotify ctypes wrapper '''
    try:
        return load_inotify.inotify
    except AttributeError:
        libc = ctypes.CDLL(None, use_errno=True)
        for function in ("inotify_add_watch", "inotify_init1", "inotify_rm_watch"):
            if not hasattr(libc, function):
                raise RuntimeError('libc is too old')
        # inotify_init1()
        prototype = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_int, use_errno=True)
        init1 = prototype(('inotify_init1', libc), ((1, "flags", 0),))

        # inotify_add_watch()
        prototype = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint32, use_errno=True)
        add_watch = prototype(('inotify_add_watch', libc), (
            (1, "fd"), (1, "pathname"), (1, "mask")), use_errno=True)

        # inotify_rm_watch()
        prototype = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_int, ctypes.c_int, use_errno=True)
        rm_watch = prototype(('inotify_rm_watch', libc), (
            (1, "fd"), (1, "wd")), use_errno=True)

        load_inotify.inotify = INotify(init1, add_watch, rm_watch)
        return load_inotify.inotify
# }}}

fenc = sys.getfilesystemencoding() or 'utf-8'
if fenc == 'ascii':
    fenc = 'utf-8'
hdr = struct.Struct('iIII')


def handle_error():
    eno = ctypes.get_errno()
    extra = ''
    if eno == errno.ENOSPC:
        extra = 'You may need to increase the inotify limits on your system, via /proc/sys/inotify/max_user_*'
    raise OSError(eno, os.strerror(eno) + ' ' + extra)


def read(inotify, inotify_fd, process_event, get_name=True):
    buf = [read.buf]
    while True:
        try:
            data = os.read(inotify_fd, 5120)
        except BlockingIOError:
            break

        num = len(data)
        if num == 0:
            break
        if num < 0:
            en = ctypes.get_errno()
            if en == errno.EAGAIN:
                break  # No more data
            if en == errno.EINTR:
                continue  # Interrupted, try again
            raise OSError(en, os.strerror(en))
        buf.append(data)
    raw = b''.join(buf)
    pos = 0
    lraw = len(raw)
    while lraw - pos >= hdr.size:
        wd, mask, cookie, name_len = hdr.unpack_from(raw, pos)
        pos += hdr.size
        name = None
        if get_name:
            name = raw[pos:pos + name_len].rstrip(b'\0').decode(fenc)
        pos += name_len
        process_event(wd, mask, cookie, name)
    read.buf = raw[pos:]
read.buf = b''


def realpath(x):
    return os.path.abspath(os.path.realpath(x))


class TreeWatcher:

    def __init__(self, basedir, ignore_event=lambda path, name: False):
        self.os = os
        self.inotify = load_inotify()
        self.inotify_fd = self.inotify.init1(os.O_CLOEXEC | os.O_NONBLOCK)
        if self.inotify_fd == -1:
            raise EnvironmentError(os.strerror(ctypes.get_errno()))
        self.basedir = realpath(basedir)
        self.ignore_event = ignore_event
        self.modified = False
        self.watch_tree()

    def fileno(self):
        return self.inotify_fd

    def close(self):
        try:
            self.os.close(self.inotify_fd)
        except AttributeError:
            pass
        else:
            del self.os

    def __del__(self):
        self.close()

    def read(self, get_name=True):
        read(self.inotify, self.inotify_fd, self.process_event, get_name=get_name)

    def watch_tree(self):
        self.watched_dirs = {}
        self.watched_rmap = {}
        try:
            self.add_watches(self.basedir, top_level=True)
        except OSError as e:
            if e.errno == errno.ENOSPC:
                raise DirTooLarge(self.basedir)

    def add_watches(self, base, top_level=False):
        ''' Add watches for this directory and all its descendant directories,
        recursively. '''
        base = realpath(base)
        # There may exist a link which leads to an endless
        # add_watches loop or to maximum recursion depth exceeded
        if not top_level and base in self.watched_dirs:
            return
        try:
            is_dir = self.add_watch(base)
        except OSError as e:
            if e.errno == errno.ENOENT:
                # The entry could have been deleted between listdir() and
                # add_watch().
                if top_level:
                    raise ValueError('The dir {0} does not exist'.format(base))
                return
            if e.errno == errno.EACCES:
                # We silently ignore entries for which we dont have permission,
                # unless they are the top level dir
                if top_level:
                    raise ValueError('You do not have permission to monitor {0}'.format(base))
                return
            raise
        else:
            if is_dir:
                try:
                    files = os.listdir(base)
                except OSError as e:
                    if e.errno in (errno.ENOTDIR, errno.ENOENT):
                        # The dir was deleted/replaced between the add_watch()
                        # and listdir()
                        if top_level:
                            raise ValueError('The dir {0} does not exist'.format(base))
                        return
                    raise
                for x in files:
                    self.add_watches(os.path.join(base, x), top_level=False)
            elif top_level:
                # The top level dir is a file, not good.
                raise ValueError('The dir {0} does not exist'.format(base))

    def add_watch(self, path):
        bpath = path if isinstance(path, bytes) else path.encode(fenc)
        wd = self.inotify.add_watch(self.inotify_fd, ctypes.c_char_p(bpath),
                                    # Ignore symlinks and watch only directories
                                    DONT_FOLLOW | ONLYDIR |

                                    MODIFY | CREATE | DELETE |
                                    MOVE_SELF | MOVED_FROM | MOVED_TO |
                                    ATTRIB | DELETE_SELF)
        if wd == -1:
            eno = ctypes.get_errno()
            if eno == errno.ENOTDIR:
                return False
            raise OSError(eno, 'Failed to add watch for: {0}: {1}'.format(path, self.os.strerror(eno)))
        self.watched_dirs[path] = wd
        self.watched_rmap[wd] = path
        return True

    def process_event(self, wd, mask, cookie, name):
        if wd == -1 and (mask & self.Q_OVERFLOW):
            # We missed some INOTIFY events, so we dont
            # know the state of any tracked dirs.
            self.watch_tree()
            self.modified = True
            return
        path = self.watched_rmap.get(wd, None)
        if path is not None:
            if not self.ignore_event(path, name):
                self.modified = True
            if mask & CREATE:
                # A new sub-directory might have been created, monitor it.
                try:
                    self.add_watch(os.path.join(path, name))
                except OSError as e:
                    if e.errno == errno.ENOENT:
                        # Deleted before add_watch()
                        pass
                    elif e.errno == errno.ENOSPC:
                        raise DirTooLarge(self.basedir)
                    else:
                        raise
            if (mask & DELETE_SELF or mask & MOVE_SELF) and path == self.basedir:
                raise ValueError('The directory %s was moved/deleted' % path)

    def was_modified_since_last_call(self):
        ret, self.modified = self.modified, False
        return ret


tree_watchers = {}
existing_watches = {}


def prune_watchers(limit=2):
    limit *= 3600
    remove = []
    now = monotonic()
    for w, last_time in tree_watchers.items():
        if now - last_time > limit:
            remove.append(w)
    for w in remove:
        del existing_watches[w.basedir]
        del tree_watchers[w]


def add_tree_watch(basedir, ignore_event=lambda path, name: False):
    basedir = realpath(basedir)
    if basedir in existing_watches:
        w = existing_watches[basedir]
    else:
        w = TreeWatcher(basedir, ignore_event=ignore_event)
        existing_watches[w.basedir] = w
    tree_watchers[w] = monotonic()
    return w
