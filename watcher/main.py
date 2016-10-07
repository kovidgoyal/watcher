#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>

import argparse
import os

from .constants import appname
from .utils import realpath


def server(args):
    from .server import run_server
    run_server(args)


def client(args):
    from .client import main
    if not hasattr(args, 'q'):
        raise SystemExit('You must specify the query to make of the server')
    main(args)


def is_ssh():
    return 'SSH_CLIENT' in os.environ or 'SSH_TTY' in os.environ


def parser():
    parser = argparse.ArgumentParser(prog=appname, description='Run the watcher')
    subparsers = parser.add_subparsers(help='Choose whether to run in server or client mode')
    s = subparsers.add_parser('server')
    s.add_argument('action', default='run', choices='run kill restart'.split(), nargs='?',
                   help='The action to perform')
    s.add_argument('--daemonize', default=False, action='store_true',
                   help='Run the server as a background daemon')
    s.add_argument('--log', default=os.devnull, help='Log file when daemonized')
    s.set_defaults(func=server)

    c = subparsers.add_parser('client')
    c.set_defaults(func=client)
    subparsers = c.add_subparsers(help='Choose query to make of the server')

    v = subparsers.add_parser('vcs', help='Query the VCS status of a directory')
    v.add_argument('path', help='Path of directory or file to query')
    v.add_argument('--both', action='store_true', help='If True, both the repo status and the status of the file passed in as path will be queried')
    v.set_defaults(q='vcs')

    v = subparsers.add_parser('watch', help='Check if a directory tree has changed since the last call')
    v.add_argument('path', help='Path of directory to query')
    v.set_defaults(q='watch')

    v = subparsers.add_parser('prompt', help='Get a nice rendered prompt for use with PS1/RPS1')
    v.add_argument('which', choices=('left', 'right'), help='left or right prompt')
    v.add_argument('--cwd', default=realpath(os.getcwd()), help='The current working directory for this query')
    v.add_argument('--home', default=realpath(os.path.expanduser('~')), help='The home directory')
    v.add_argument('--user', default=os.environ.get('USER', os.path.basename(os.path.expanduser('~'))),
                   help='The current username')
    v.add_argument('--last-exit-code', default='0', help='The last exit code to display')
    v.add_argument('--last-pipe-code', default='0', help='The last pipe exit code to display')
    v.add_argument('--is-ssh', default='1' if is_ssh() else '0', help='Set to 1 if this is an SSH session')
    v.set_defaults(q='prompt')

    return parser


def main():
    args = parser().parse_args()
    getattr(args, 'func', client)(args)
