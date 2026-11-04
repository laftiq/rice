"""Anchor a panel popup below the clicked element, within its monitor."""
import gi

gi.require_version('Gdk', '3.0')
from gi.repository import Gdk

_anchor = None


def popup_args(width, edge_gap=0):
    global _anchor
    try:
        if _anchor is None:
            Gdk.init([])
            display = Gdk.Display.get_default()
            pointer = display.get_default_seat().get_pointer()
            _, x, y = pointer.get_position()
            monitor = display.get_monitor_at_point(x, y)
            rect = monitor.get_geometry()
            index = next(i for i in range(display.get_n_monitors())
                         if display.get_monitor(i) == monitor)
            _anchor = (x - rect.x, rect.width, index)
        x, monitor_width, index = _anchor
        # Increase the rightward shift smoothly for buttons farther left.
        shift = round(160 * (1 - max(0, min(x / monitor_width, 1))))
        left = max(8, min(x - width // 2 + shift, monitor_width - width - edge_gap))
        style = ('window { location: northwest; anchor: northwest; '
                 f'x-offset: {left}px; y-offset: 38px; }}')
        return ['-monitor', str(index), '-theme-str', style]
    except (AttributeError, ValueError, StopIteration) as error:
        from pathlib import Path
        (Path.home()/'.cache/rice/popup-position-error.log').write_text(repr(error))
        return []
