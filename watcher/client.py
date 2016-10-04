#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>
from __future__ import absolute_import, unicode_literals

import socket
import errno
import functools

from .constants import local_socket_address
from .utils import serialize_message, deserialize_message, realpath

is_cli = False


def send_msg(s, msg):
    s.sendall(serialize_message(msg))
    s.shutdown(socket.SHUT_WR)


def recv_msg(s, ds=deserialize_message):
    buf = b''
    while True:
        d = s.recv(4096)
        if d:
            buf += d
        else:
            break
    try:
        return ds(buf)
    finally:
        s.shutdown(socket.SHUT_RDWR)
        s.close()


def entry(f):
    @functools.wraps(f)
    def wrapper(args):
        s = connect()
        if s is None:
            raise (SystemExit if is_cli else EnvironmentError)('No running daemon found at: ' + local_socket_address())
        return f(s, args)
    return wrapper


def connect():
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        s.connect(local_socket_address())
    except EnvironmentError as err:
        if err.errno == errno.ENOENT:
            return None
        raise
    return s


@entry
def vcs(s, args):
    send_msg(s, {'q': 'vcs', 'path': realpath(args.path)})
    print(recv_msg(s))


@entry
def watch(s, args):
    send_msg(s, {'q': 'watch', 'path': realpath(args.path)})
    print(recv_msg(s))


@entry
def prompt(s, args):
    send_msg(s, {'q': 'prompt', 'which': args.which, 'cwd': realpath(args.cwd), 'last_exit_code': args.last_exit_code,
                 'last_pipe_code': args.last_pipe_code})
    print(recv_msg(s, ds=lambda x: x.decode('utf-8')))


def main(args):
    global is_cli
    is_cli = True
    if args.q == 'prompt':
        return prompt(args)
    elif args.q == 'vcs':
        return vcs(args)
    elif args.q == 'watch':
        return watch(args)
    raise SystemExit('Unknown query: {}'.format(args.q))
