#!/usr/bin/python3
"""Supply the StatusNotifier watcher missing from a Polybar-only session.

No tray widgets are drawn. Happ's native menu is consumed by happ-menu.py.
Do not replace a watcher supplied by an existing desktop panel.
"""
import gi
gi.require_version('Gio', '2.0')
from gi.repository import Gio, GLib

SERVICE = 'org.kde.StatusNotifierWatcher'
PATH = '/StatusNotifierWatcher'
XML = '''<node><interface name="org.kde.StatusNotifierWatcher">
<method name="RegisterStatusNotifierItem"><arg type="s" direction="in"/></method>
<method name="RegisterStatusNotifierHost"><arg type="s" direction="in"/></method>
<property name="RegisteredStatusNotifierItems" type="as" access="read"/>
<property name="IsStatusNotifierHostRegistered" type="b" access="read"/>
<property name="ProtocolVersion" type="i" access="read"/>
<signal name="StatusNotifierItemRegistered"><arg type="s"/></signal>
<signal name="StatusNotifierItemUnregistered"><arg type="s"/></signal>
<signal name="StatusNotifierHostRegistered"/>
<signal name="StatusNotifierHostUnregistered"/>
</interface></node>'''


class Watcher:
    def __init__(self, bus):
        self.bus = bus
        self.items = {}
        self.registration = bus.register_object(
            PATH, Gio.DBusNodeInfo.new_for_xml(XML).interfaces[0],
            self.method, self.property, None)
        self.subscription = bus.signal_subscribe(
            'org.freedesktop.DBus', 'org.freedesktop.DBus', 'NameOwnerChanged',
            '/org/freedesktop/DBus', None, Gio.DBusSignalFlags.NONE,
            self.owner_changed)

    def signal(self, name, item):
        self.bus.emit_signal(None, PATH, SERVICE, name, GLib.Variant('(s)', (item,)))

    def method(self, bus, sender, path, interface, method, parameters, invocation):
        value = parameters.unpack()[0]
        if method == 'RegisterStatusNotifierItem':
            service = sender if value.startswith('/') else value
            item_path = value if value.startswith('/') else '/StatusNotifierItem'
            if not service or not item_path.startswith('/'):
                invocation.return_dbus_error('org.freedesktop.DBus.Error.InvalidArgs',
                                             'Invalid notifier service or path')
                return
            item = service + item_path
            if item not in self.items:
                self.items[item] = sender
                self.signal('StatusNotifierItemRegistered', item)
        invocation.return_value(GLib.Variant('()', ()))

    def property(self, bus, sender, path, interface, name):
        if name == 'RegisteredStatusNotifierItems':
            return GLib.Variant('as', list(self.items))
        if name == 'IsStatusNotifierHostRegistered':
            return GLib.Variant('b', True)
        if name == 'ProtocolVersion':
            return GLib.Variant('i', 0)
        return None

    def owner_changed(self, bus, sender, path, interface, signal, parameters):
        name, old, new = parameters.unpack()
        if old and not new:
            for item, owner in list(self.items.items()):
                if name == owner or item.startswith(name + '/'):
                    del self.items[item]
                    self.signal('StatusNotifierItemUnregistered', item)


def main():
    bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    # DO_NOT_QUEUE: an existing LXQt/KDE watcher takes precedence.
    reply = bus.call_sync('org.freedesktop.DBus', '/org/freedesktop/DBus',
                         'org.freedesktop.DBus', 'RequestName',
                         GLib.Variant('(su)', (SERVICE, 4)), None,
                         Gio.DBusCallFlags.NONE, 2000, None).unpack()[0]
    if reply != 1:
        return
    watcher = Watcher(bus)
    bus.emit_signal(None, PATH, SERVICE, 'StatusNotifierHostRegistered', None)
    GLib.MainLoop().run()


if __name__ == '__main__':
    main()
