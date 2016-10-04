#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>

import sys
import socket
import select

from .constants import local_socket_address
from .utils import deserialize_message, serialize_message

read_needed, write_needed = set(), set()
clients = {}


def log_error(*args, **kw):
    kw['file'] = sys.stderr
    print(*args, **kw)


def handle_msg(msg):
    return msg


def tick(serversocket):
    try:
        readable, writable, _ = select.select([serversocket] + list(read_needed), list(write_needed), [], 60)
    except ValueError:
        log_error('Listening socket was unexpectedly terminated')
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
                    msg = deserialize_message(data['rbuf'])
                except Exception:
                    del clients[c]
                    c.close()
                    continue
                del data['rbuf']
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
        except KeyboardInterrupt:
            raise SystemExit(0)


def run_server(args):
    serversocket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    serversocket.bind(local_socket_address())
    serversocket.setblocking(0)
    serversocket.listen(5)
    run_loop(serversocket)
