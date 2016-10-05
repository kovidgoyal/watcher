#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>
from __future__ import unicode_literals

from functools import partial
from collections import namedtuple

from .utils import print_error

BT = namedtuple('BatteryTime', 'charging percentage hours minutes')


def do_find_battery():
    try:
        import dbus
    except ImportError:
        print_error('Cannot get battery stats as DBUS not available')
        return
    bus = dbus.SystemBus()
    try:
        up = bus.get_object('org.freedesktop.UPower', '/org/freedesktop/UPower')
    except dbus.exceptions.DBusException as e:
        if getattr(e, '_dbus_error_name', None) == 'org.freedesktop.DBus.Error.ServiceUnknown':
            print_error('Cannot get batter stats as UPower service is not available')
            return
        raise
    for devpath in up.EnumerateDevices(dbus_interface='org.freedesktop.UPower'):
        dev = bus.get_object('org.freedesktop.UPower', devpath)
        devtype = int(dev.Get('org.freedesktop.UPower.Device', 'Type', dbus_interface='org.freedesktop.DBus.Properties'))
        if devtype != 2:
            continue
        if not bool(dev.Get('org.freedesktop.UPower.Device', 'IsPresent', dbus_interface='org.freedesktop.DBus.Properties')):
            continue
        if not bool(dev.Get('org.freedesktop.UPower.Device', 'PowerSupply', dbus_interface='org.freedesktop.DBus.Properties')):
            continue
        return partial(dbus.Interface(dev, dbus_interface='org.freedesktop.DBus.Properties').Get, 'org.freedesktop.UPower.Device')


def find_battery():
    if not hasattr(find_battery, 'ans'):
        find_battery.ans = do_find_battery()
    return find_battery.ans


def battery_time():
    dev = find_battery()
    if dev is None:
        return None
    state = int(dev('State'))
    if state not in (1, 2):
        return None
    tleft = int(dev('TimeToFull' if state == 1 else 'TimeToEmpty'))
    percentage = float(dev('Percentage'))
    if tleft == 0:
        return None
    minutes = tleft // 60
    hours, minutes = minutes // 60, minutes % 60
    return BT(state == 1, percentage, hours, minutes)
