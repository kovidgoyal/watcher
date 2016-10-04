#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>

import argparse

from .constants import appname


def server(args):
    from .server import run_server
    run_server(args)


def client(args):
    from .client import main
    if not hasattr(args, 'q'):
        raise SystemExit('You must specify the query to make of the server')
    main(args)


def parser():
    parser = argparse.ArgumentParser(prog=appname, description='Run the watcher')
    subparsers = parser.add_subparsers(help='Choose whether to run in server or client mode')
    s = subparsers.add_parser('server')
    s.set_defaults(func=server)

    c = subparsers.add_parser('client')
    c.set_defaults(func=client)
    subparsers = c.add_subparsers(help='Choose query to make of the server')
    v = subparsers.add_parser('vcs', help='Query the VCS status of a directory')
    v.add_argument('path', nargs=1, help='Path of directory to query')
    v.set_defaults(q='vcs')
    return parser


def main():
    args = parser().parse_args()
    getattr(args, 'func', client)(args)
