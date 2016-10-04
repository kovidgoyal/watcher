#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>

import sys
import socket
import select
import errno
import traceback
from time import monotonic

from .constants import local_socket_address
from .utils import deserialize_message, serialize_message, String
from .inotify import tree_watchers, prune_watchers, add_tree_watch
from .vcs import vcs_data
from .prompt import prompt_data

read_needed, write_needed = set(), set()
clients = {}


def print_error(*args, **kw):
    kw['file'] = sys.stderr
    print(*args, **kw)


def handle_msg(msg):
    q = msg.get('q')
    try:
        if q == 'prompt':
            return String(prompt_data(**msg))
        if q == 'vcs':
            ans = vcs_data(msg['path'], subpath=msg.get('subpath'))
            ans['ok'] = True
            return ans
        if q == 'watch':
            w = add_tree_watch(msg['path'])
            return {'ok': True, 'modified': w.was_modified_since_last_call()}
    except Exception as err:
        return {'ok': False, 'msg': str(err), 'tb': traceback.format_exc()}

    return {'ok': False, 'msg': 'Query: {} not understood'.format(q), 'tb': ''}


def tick(serversocket):
    try:
        readable, writable, _ = select.select([serversocket] + list(read_needed) + list(tree_watchers), list(write_needed), [])
    except ValueError:
        print_error('Listening socket was unexpectedly terminated')
        raise SystemExit(1)
    for s in readable:
        if s is serversocket:
            try:
                c = s.accept()[0]
            except socket.error:
                pass
            else:
                read_needed.add(c)
                clients[c] = {'rbuf': b''}
        elif s in tree_watchers:
            try:
                s.read()
            except Exception:
                print_error(traceback.format_exc())
                s.close()
                del tree_watchers[s]
            else:
                tree_watchers[s] = monotonic()
        else:
            c = s
            data = clients.get(c)
            if data is None:
                c.close()
                readable.discard(c)
                continue
            d = c.recv(4096)
            if d:
                data['rbuf'] += d
            else:
                read_needed.discard(c)
                try:
                    msg = deserialize_message(data.pop('rbuf'))
                except Exception:
                    del clients[c]
                    c.close()
                    continue
                try:
                    data['wbuf'] = serialize_message(handle_msg(msg))
                except Exception:
                    del clients[c]
                    c.close()
                else:
                    write_needed.add(c)

    for c in writable:
        data = clients.get(c)
        if data is None:
            writable.discard(c)
            c.close()
            continue
        n = c.send(data['wbuf'])
        if n > 0:
            data['wbuf'] = data['wbuf'][n:]
        if not data['wbuf']:
            write_needed.discard(c)
            c.close()
            del clients[c]


def run_loop(serversocket):
    while True:
        try:
            tick(serversocket)
            prune_watchers()
        except KeyboardInterrupt:
            raise SystemExit(0)


def run_server(args):
    serversocket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        serversocket.bind(local_socket_address())
    except EnvironmentError as err:
        if err.errno == errno.EADDRINUSE:
            raise SystemExit('The daemon is already running')
        raise
    serversocket.setblocking(0)
    serversocket.listen(5)
    run_loop(serversocket)
