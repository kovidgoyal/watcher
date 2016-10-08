#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>
from __future__ import unicode_literals, print_function, division

import os
from collections import defaultdict, deque

try:
    from .utils import print_error
except ValueError:
    print_error = print


def BT(charging, percentage, hours, minutes):
    return locals()


def read(path, is_unit=True):
    try:
        with open(path, 'rb') as f:
            val = f.read().decode('ascii').strip()
        if is_unit:
            val = int(val) / 1e6
        else:
            val = val.lower()
    except Exception:
        raise
        val = None
    return val


def effective_rate(history, current_val):
    history.append(current_val)
    return sum(history) / len(history)


def battery_time():
    base = '/sys/class/power_supply'
    ans = []
    for x in os.listdir(base):
        if x == 'AC':
            continue
        data = {}
        for k in ('power_now', 'energy_now', 'energy_full'):
            val = data[k] = read(os.path.join(base, x, k))
            if val is None:
                break
        else:
            state = read(os.path.join(base, x, 'status'), False)
            if state in ('charging', 'discharging'):
                power = effective_rate(battery_time.history[x][state], data['power_now'])
                t = data['energy_now'] / power
                ans.append(BT(state == 'charging', 100 * data['energy_now'] / data['energy_full'], int(t), int(60 * (t - int(t)))))
    return ans

battery_time.history = defaultdict(lambda: {'charging': deque(maxlen=60), 'discharging': deque(maxlen=60)})


if __name__ == '__main__':
    print(battery_time())
