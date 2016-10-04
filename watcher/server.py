#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>

import sys
import os
import re
import socket
import signal
import time
import select
import errno
import traceback
from time import monotonic

from .constants import local_socket_address
from .utils import deserialize_message, serialize_message, String, readlines
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
            try:
                return String(prompt_data(**msg))
            except Exception as err:
                print_error(traceback.format_exc())
                return String(err)
        if q == 'vcs':
            ans = vcs_data(msg['path'], subpath=msg.get('subpath'))
            ans['ok'] = True
            return ans
        if q == 'watch':
            w = add_tree_watch(msg['path'])
            return {'ok': True, 'modified': w.was_modified_since_last_call()}
    except Exception as err:
        print_error(traceback.format_exc())
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
        try:
            n = c.send(data['wbuf'])
        except BrokenPipeError:
            data['wbuf'] = b''
            n = 0
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


def daemonize(stdin=os.devnull, stdout=os.devnull, stderr=os.devnull):
    try:
        pid = os.fork()
        if pid > 0:
            # exit first parent
            sys.exit(0)
    except OSError as e:
        raise SystemExit("fork #1 failed: %d (%s)" % (e.errno, e.strerror))

    # decouple from parent environment
    os.chdir("/")
    os.setsid()
    os.umask(0)

    # do second fork
    try:
        pid = os.fork()
        if pid > 0:
            # exit from second parent
            sys.exit(0)
    except OSError as e:
        raise SystemExit("fork #1 failed: %d (%s)" % (e.errno, e.strerror))
        sys.exit(1)

    # Redirect standard file descriptors.
    si = open(stdin, 'rb')
    so = open(stdout, 'a+b')
    se = open(stderr, 'a+b', 0)
    os.dup2(si.fileno(), sys.stdin.fileno())
    os.dup2(so.fileno(), sys.stdout.fileno())
    os.dup2(se.fileno(), sys.stderr.fileno())


def pid_of_running_server():
    q = local_socket_address().replace(b'\0', b'@')
    for line in readlines('ss -xlnp'.split(), decode=False):
        parts = line.split()
        if q in parts:
            m = re.search(br'pid=(\d+)', line)
            if m is not None:
                return int(m.group(1))


def kill():
    pid = pid_of_running_server()
    if pid is None:
        print('No running server')
    else:
        os.kill(pid, signal.SIGINT)
        for i in range(3):
            time.sleep(0.1)
            pid = pid_of_running_server()
            if pid is None:
                break
        if pid is not None:
            os.kill(pid, signal.SIGTERM)
            time.sleep(0.2)
            pid = pid_of_running_server()
            if pid is not None:
                os.kill(pid, signal.SIGKILL)


def run_server(args):
    if args.action == 'kill':
        return kill()
    elif args.action == 'restart':
        kill()
    if args.daemonize:
        daemonize(stdout=args.log, stderr=args.log)
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
