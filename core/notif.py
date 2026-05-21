# notif.py — Overlay notifications OLED
from core import hw
import time

_msg   = None
_until = 0

def push(txt, ms=3000):
    global _msg, _until
    _msg = str(txt)[:32]; _until = time.ticks_ms() + ms
    hw.touch()

def clear():
    global _msg, _until
    _msg = None; _until = 0

def tick():
    global _msg, _until
    if not _msg: return False
    if time.ticks_diff(time.ticks_ms(), _until) > 0:
        clear(); return False
    hw.oled.fill_rect(2, 44, 124, 18, 0)
    hw.oled.rect(2, 44, 124, 18, 1)
    l1, l2 = _msg[:16], _msg[16:]
    hw.oled.text(l1, hw.cx(l1), 46)
    if l2: hw.oled.text(l2, hw.cx(l2), 55)
    hw.oled.show()
    return True

def get():
    return _msg if _msg and time.ticks_diff(time.ticks_ms(), _until) < 0 else None
