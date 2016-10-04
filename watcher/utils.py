#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>

import json


def deserialize_message(raw):
    return json.loads(raw.decode('utf-8'))


def serialize_message(msg):
    return json.dumps(msg, ensure_ascii=False).encode('utf-8')
