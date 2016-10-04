#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>
from __future__ import absolute_import, unicode_literals

import socket
import errno
import os

from .constants import local_socket_address
from .utils import serialize_message, deserialize_message

is_cli = False


def send_msg(s, msg):
    s.sendall(serialize_message(msg))
    s.shutdown(socket.SHUT_WR)


def recv_msg(s):
    buf = b''
    while True:
        d = s.recv(4096)
        if d:
            buf += d
        else:
            break
    try:
        return deserialize_message(buf)
    finally:
        s.shutdown(socket.SHUT_RDWR)
        s.close()


def connect():
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        s.connect(local_socket_address())
    except EnvironmentError as err:
        if err.errno == errno.ENOENT:
            return None
        raise
    return s


def vcs(path):
    s = connect()
    if s is None:
        raise (SystemExit if is_cli else EnvironmentError)('No running daemon found at: ' + local_socket_address())
    send_msg(s, {'q': 'vcs', 'path': os.path.abspath(path)})
    print(recv_msg(s))


def main(args):
    global is_cli
    is_cli = True
    if args.q == 'vcs':
        return vcs(args.path[0])
    raise SystemExit('Unknown query: {}'.format(args.q))
