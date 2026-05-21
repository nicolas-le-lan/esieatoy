# boot.py — Premier fichier exécuté par MicroPython au démarrage
import gc, sys

for p in ("/", ""):
    if p not in sys.path:
        sys.path.insert(0, p)

gc.collect()

try:
    import config as C
    from machine import Pin, SoftI2C
    _i2c = SoftI2C(scl=Pin(C.OLED_SCL), sda=Pin(C.OLED_SDA), freq=400_000)

    _d = None
    try:
        import drivers.sh1106 as _d
    except ImportError:
        try:
            import sh1106 as _d
        except ImportError:
            pass

    if _d is not None:
        _oled = _d.SH1106_I2C(C.W, C.H, _i2c, addr=C.OLED_ADDR)
        _oled.fill(0)

        # ── Logo tablette ESIEA TOY 16×16 centré ─────────────
        _LOGO = [
            0x0000,0x1FF8,0x2004,0x2494,0x2004,0x27F4,0x27F4,0x27F4,
            0x27F4,0x27F4,0x2004,0x23C4,0x2004,0x1FF8,0x0000,0x0000,
        ]
        _sx, _sy = (C.W - 16) // 2, 4
        for _r, _row in enumerate(_LOGO):
            for _b in range(16):
                if _row & (1 << (15 - _b)):
                    _oled.pixel(_sx + _b, _sy + _r, 1)

        # ── Textes ───────────────────────────────────────────
        _oled.text("ESIEA TOY OS",  16, 26, 1)   # 12 chars × 8 = 96 px → x=16
        _oled.text("Caraibes, 1700", 8, 36, 1)   # 14 chars × 8 = 112 px → x=8
        _oled.hline(24, 48, 80, 1)
        _oled.text("Chargement...", 12, 54, 1)   # 13 chars × 8 = 104 px → x=12

        _oled.show()
        del _oled, _d, _LOGO
    del _i2c
except Exception as _e:
    print("[boot] splash erreur:", _e)

gc.collect()
