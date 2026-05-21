# =============================================================================
# core/hw.py — Couche matériel Badge ESE (ESP32-C3 · MicroPython)
# =============================================================================
# Ce module est le singleton hardware de l'OS.
# Il gère : OLED I2C, LED RGB, Buzzer PWM, Boutons avec debounce, Batterie ADC.
# Importer avec : from core import hw
# =============================================================================
from machine import Pin, SoftI2C, PWM
import time, gc, machine
import config as C
from core import store

try:
    from machine import ADC as _ADC
except ImportError:
    _ADC = None


# ── DummyOLED — évite les boot loops si l'écran est absent ───────────────────
class _DummyOLED:
    width = C.W; height = C.H
    def fill(self, c):                          pass
    def text(self, t, x, y, c=1):              pass
    def show(self):                             pass
    def pixel(self, x, y, c):                  pass
    def rect(self, x, y, w, h, c):             pass
    def fill_rect(self, x, y, w, h, c):        pass
    def hline(self, x, y, w, c):               pass
    def vline(self, x, y, h, c):               pass
    def ellipse(self, x, y, rx, ry, c):        pass
    def contrast(self, l):                      pass
    def poweron(self):                          pass
    def poweroff(self):                         pass
    def write_cmd(self, cmd):                   pass


# ── OLED : initialisation avec auto-détection du driver ──────────────────────
i2c = SoftI2C(scl=Pin(C.OLED_SCL), sda=Pin(C.OLED_SDA), freq=400000)
oled = None
W    = C.W
H    = C.H
_oled_type = "none"

def _init_oled():
    global oled, H, _oled_type

    # Load SH1106 driver (hardware on this badge)
    _sh1106 = None; _ssd1306 = None
    try:
        import drivers.sh1106 as _sh1106
    except ImportError:
        try:
            import sh1106 as _sh1106
        except ImportError:
            pass
    # Load SSD1306 driver (fallback)
    try:
        import drivers.ssd1306 as _ssd1306
    except ImportError:
        try:
            import ssd1306 as _ssd1306
        except ImportError:
            pass

    if _ssd1306 is None and _sh1106 is None:
        print("[hw] CRITIQUE: aucun driver OLED disponible")
        oled = _DummyOLED(); _oled_type = "dummy"; return

    # SH1106 toujours en premier : le driver SSD1306 "réussit" sur SH1106 mais
    # corrompt l'affichage (0x7F interprété comme display-start-line=63).
    # La pref stockée est ignorée pour l'ordre ; elle garde seulement la trace du
    # driver qui a fonctionné pour d'éventuels réglages avancés.
    order = []
    if _sh1106:  order.append(("sh1106",  _sh1106.SH1106_I2C))
    if _ssd1306: order.append(("ssd1306", _ssd1306.SSD1306_I2C))

    for height in (64, 32):
        for name, cls in order:
            try:
                oled = cls(W, height, i2c, addr=C.OLED_ADDR)
                H = height; _oled_type = name
                store.put("sys", "oled", name)
                print("[hw] OLED:", name, W, "x", H)
                return
            except Exception as e:
                print("[hw] OLED", name, height, ":", e)

    print("[hw] CRITIQUE: OLED introuvable, DummyOLED activé")
    oled = _DummyOLED(); _oled_type = "dummy"

_init_oled()


# ── LED RGB — anode commune (0=allumé, 1=éteint) ─────────────────────────────
_lr = Pin(C.PIN_LR, Pin.OUT, value=1)
_lg = Pin(C.PIN_LG, Pin.OUT, value=1)
_lb = Pin(C.PIN_LB, Pin.OUT, value=1)

def led(r=0, g=0, b=0):
    """Active les canaux R/G/B (True = allumé)."""
    _lr.value(0 if r else 1)
    _lg.value(0 if g else 1)
    _lb.value(0 if b else 1)

def led_off():     led(0, 0, 0)
def led_red():     led(1, 0, 0)
def led_green():   led(0, 1, 0)
def led_blue():    led(0, 0, 1)
def led_yellow():  led(1, 1, 0)
def led_cyan():    led(0, 1, 1)
def led_magenta(): led(1, 0, 1)
def led_white():   led(1, 1, 1)

def led_blink(r=0, g=0, b=0, times=3, ms=80):
    """Clignotement N fois."""
    for _ in range(times):
        led(r, g, b); time.sleep_ms(ms)
        led_off();    time.sleep_ms(ms)


# ── Buzzer PWM passif ─────────────────────────────────────────────────────────
_bz = PWM(Pin(C.PIN_BZ), freq=440, duty=0)

def _vol():
    v = store.get("sound", "volume", 2)
    return {1: 80, 2: 350, 3: 750}.get(v, 350)

def tone(freq, ms):
    """
    Joue une note à `freq` Hz pendant `ms` ms.
    freq <= 0 = silence (pause rythmique).
    """
    if not store.get("sound", "on", True):
        time.sleep_ms(ms); return
    if freq <= 0:
        time.sleep_ms(ms); return
    try:
        _bz.freq(max(1, int(freq)))
        _bz.duty(_vol())
    except:
        pass
    time.sleep_ms(ms)
    _bz.duty(0)

def melody(notes):
    """
    Joue une séquence de notes.
    notes = [(fréq_hz, durée_ms), ...]
    """
    for f, ms in notes:
        tone(f, ms)
        time.sleep_ms(12)   # respiration inter-notes

def beep():
    tone(1000, 25)


# ── Boutons — PULL_DOWN actif HIGH, anti-rebond logiciel ─────────────────────
_BTNS = {
    "up": Pin(C.PIN_UP, Pin.IN, Pin.PULL_DOWN),
    "dn": Pin(C.PIN_DN, Pin.IN, Pin.PULL_DOWN),
    "lt": Pin(C.PIN_LT, Pin.IN, Pin.PULL_DOWN),
    "rt": Pin(C.PIN_RT, Pin.IN, Pin.PULL_DOWN),
    "a":  Pin(C.PIN_A,  Pin.IN, Pin.PULL_DOWN),
    "b":  Pin(C.PIN_B,  Pin.IN, Pin.PULL_DOWN),
}
_last_ts = {k: 0 for k in _BTNS}
_DBNC = C.DEBOUNCE_MS

_sys_tick_hook = None

def set_tick_hook(cb):
    global _sys_tick_hook
    _sys_tick_hook = cb

def read_btn():
    """
    Lecture non-bloquante. Retourne le nom du bouton pressé ou None.
    Le debounce est géré par timestamp : on ignore les appuis trop rapprochés.
    """
    now = time.ticks_ms()
    for k, p in _BTNS.items():
        if p.value():
            if time.ticks_diff(now, _last_ts[k]) > _DBNC:
                _last_ts[k] = now
                _last_act_update()
                return k
    return None

def wait_btn(timeout_ms=0):
    """
    Lecture bloquante. Retourne le bouton pressé, ou None si timeout.
    timeout_ms = 0 → attente infinie.
    """
    t0 = time.ticks_ms()
    while True:
        b = read_btn()
        if b:
            return b
        if timeout_ms and time.ticks_diff(time.ticks_ms(), t0) > timeout_ms:
            return None
        if _sys_tick_hook:
            _sys_tick_hook()
        time.sleep_ms(8)

def any_btn_pressed():
    """Retourne True si au moins un bouton est physiquement pressé (brut, sans debounce)."""
    return any(p.value() for p in _BTNS.values())


# ── Helpers OLED ──────────────────────────────────────────────────────────────
def oled_show():
    """Envoie le framebuffer vers l'écran. Silencieux en cas d'erreur."""
    try:
        oled.show()
    except Exception as e:
        print("[hw] oled.show:", e)

def cls():
    oled.fill(0); oled_show()

def cx(text, offset=0):
    """Coordonnée X pour centrer `text` horizontalement (police 8px)."""
    return offset + max(0, (W - offset - len(str(text)) * 8) // 2)

def set_contrast(level):
    try: oled.contrast(level)
    except: pass


# ── Veille écran ──────────────────────────────────────────────────────────────
_last_act = time.ticks_ms()
_awake    = True

def _last_act_update():
    global _last_act
    _last_act = time.ticks_ms()

def touch():
    """Signale une activité utilisateur (réinitialise le timer de veille)."""
    _last_act_update()

def wake():
    """Réveille l'écran."""
    global _awake
    if not _awake:
        _awake = True
        try:
            if _oled_type == "sh1106": oled.write_cmd(0xAF)
            else:                       oled.poweron()
        except: pass

def sleep_tick():
    """
    Appelé dans la boucle principale. Éteint l'écran si inactif trop longtemps.
    Retourne True si l'écran vient d'être éteint.
    """
    global _awake
    if not _awake:
        return False
    ms = store.get("display", "sleep_ms", C.SLEEP_MS)
    if ms > 0 and time.ticks_diff(time.ticks_ms(), _last_act) > ms:
        try:
            if _oled_type == "sh1106": oled.write_cmd(0xAE)
            else:                       oled.poweroff()
        except: pass
        led_off()
        _awake = False
        return True
    return False

def is_awake():
    return _awake


# ── Batterie ADC ──────────────────────────────────────────────────────────────
_bat_adc = None
_BAT_EN  = getattr(C, "BAT_ENABLED", False)
if _BAT_EN and _ADC is not None:
    try:
        _bat_adc = _ADC(Pin(C.PIN_BAT))
        _bat_adc.atten(_ADC.ATTN_11DB)
    except:
        pass

def get_battery_voltage():
    if not _bat_adc: return 0.0
    try:
        avg = sum(_bat_adc.read() for _ in range(8)) / 8
        return round((avg * 3.6 / 4095) * C.BAT_DIV, 2)
    except: return 0.0

def get_battery_percent():
    if not _bat_adc: return 100  # USB = toujours "plein"
    v = get_battery_voltage()
    if v <= 0: return 0
    p = int((v - C.BAT_MIN) / (C.BAT_MAX - C.BAT_MIN) * 100)
    return max(0, min(100, p))

def on_battery():
    return store.get("sys", "pwr_mode", "bat") == "bat"
