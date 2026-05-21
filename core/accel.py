# =============================================================================
# core/accel.py — Driver accéléromètre LIS3DH via I2C
# =============================================================================
# Le LIS3DH partage le bus I2C avec l'écran OLED (SDA/SCL identiques).
# Il est utilisé dans deux ateliers :
#   - radio_dist.py  : inclinaison comme proxy de "distance"
#   - accel_bruit.py : amplitude des vibrations
#
# L'objet est un singleton : accel.get() retourne toujours la même instance.
# En cas d'erreur d'initialisation, une exception OSError est levée —
# les puzzles qui en dépendent catchent cette exception et utilisent
# un fallback basé sur le temps pour permettre les tests sans hardware.
# =============================================================================
import time, struct
from core import hw

_CTRL1 = 0x20   # Control register 1
_CTRL4 = 0x23   # Control register 4
_OUT_X = 0x28   # Registre de sortie X (lecture multi-octet avec bit 7 = 1)
_WHO   = 0x0F   # Who Am I
_ID    = 0x33   # Réponse attendue du LIS3DH

_instance = None


class LIS3DH:
    """
    Driver minimal pour le LIS3DH.
    Calibration automatique à l'initialisation (20 échantillons à plat).
    """

    def __init__(self):
        self._i2c  = hw.i2c
        self._addr = None

        # Scan des deux adresses possibles (0x18 et 0x19)
        for addr in (0x18, 0x19):
            try:
                who = hw.i2c.readfrom_mem(addr, _WHO, 1)[0]
                if who == _ID:
                    self._addr = addr
                    break
            except:
                pass

        if not self._addr:
            raise OSError("LIS3DH introuvable sur I2C")

        # 100 Hz, tous axes activés
        self._write(_CTRL1, 0x57)
        # Mode haute résolution, +/- 2g
        self._write(_CTRL4, 0x08)
        time.sleep_ms(100)

        print("[accel] LIS3DH @ 0x{:02X}".format(self._addr))
        self._calibrate()

    def _write(self, reg, val):
        self._i2c.writeto_mem(self._addr, reg, bytes([val]))

    def _raw(self):
        """Lit les 6 registres XYZ en une seule transaction I2C."""
        data = self._i2c.readfrom_mem(self._addr, _OUT_X | 0x80, 6)
        x, y, z = struct.unpack("<hhh", data)
        return x / 16.0, y / 16.0, z / 16.0

    def _calibrate(self):
        """Calcule le biais (offset) quand le badge est à plat."""
        sx = sy = sz = 0.0
        for _ in range(20):
            x, y, z = self._raw()
            sx += x; sy += y; sz += z
            time.sleep_ms(10)
        self._bx = sx / 20
        self._by = sy / 20
        self._bz = sz / 20

    def read(self):
        """Retourne (x, y, z) en unités brutes LIS3DH, corrigés du biais."""
        x, y, z = self._raw()
        return x - self._bx, y - self._by, z - self._bz

    def tilt(self):
        """
        Retourne (tx, ty) normalisés entre -1.0 et +1.0.
        Pratique pour l'effet parallaxe du menu.
        """
        x, y, _ = self.read()
        return (max(-1.0, min(1.0, x / 1000.0)),
                max(-1.0, min(1.0, y / 1000.0)))

    def magnitude(self):
        """Amplitude totale du vecteur accélération (pour détecter les chocs)."""
        import math
        x, y, z = self.read()
        return math.sqrt(x * x + y * y + z * z)

    def abs_x(self):
        """Valeur absolue de l'axe X (proxy de distance pour radio_dist)."""
        x, _, _ = self.read()
        return abs(x)


def get():
    """Retourne le singleton LIS3DH. Crée l'instance au premier appel."""
    global _instance
    if _instance is None:
        _instance = LIS3DH()
    return _instance
