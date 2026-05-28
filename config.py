# config.py — Constantes ESIEA TOY OS (ESP32-C3 · MicroPython)
# Seul fichier à modifier si le matériel change.

# ── OLED ──────────────────────────────────────────────────────────────────────
OLED_SDA  = 3
OLED_SCL  = 10
OLED_ADDR = 0x3C
W, H      = 128, 64

# ── LED RGB — anode commune (LOW = allumé) ────────────────────────────────────
PIN_LR, PIN_LG, PIN_LB = 20, 8, 7

# ── Buzzer PWM passif ─────────────────────────────────────────────────────────
PIN_BZ = 21

# ── Boutons — PULL_DOWN, actif HIGH ───────────────────────────────────────────
PIN_UP, PIN_DN         = 0, 1
PIN_LT, PIN_RT         = 2, 4
PIN_A,  PIN_B          = 5, 6
DEBOUNCE_MS            = 180

# ── Batterie ADC (pont diviseur x2, 2 piles AAA = max ~3.3 V) ────────────────
PIN_BAT     = 3      # partagé avec OLED SDA — désactivé par défaut
BAT_ENABLED = False  # True si un pin ADC dédié est câblé
BAT_DIV     = 2.0
BAT_MIN     = 2.6
BAT_MAX     = 3.3

# ── Réseau ────────────────────────────────────────────────────────────────────
WEB_PORT = 80
AP_IP    = "192.168.4.1"

# ── Veille écran (ms, 0 = jamais) ─────────────────────────────────────────────
SLEEP_MS = 60000

# ── Sons (fréquence Hz, durée ms) ─────────────────────────────────────────────
SND_BOOT    = [(523,80),(659,80),(784,80),(1047,160)]
SND_OK      = [(880,60),(1200,100)]
SND_WIN     = [(523,100),(659,100),(784,100),(1047,200)]
SND_LOSE    = [(392,150),(349,150),(294,300)]
SND_ERR     = [(200,350)]
SND_NAV     = [(800,35)]
SND_TICK    = [(600,20)]
SND_CONFIRM = [(880,50),(1100,80)]
SND_HINT    = [(440,60),(550,80)]
SND_UNLOCK  = [(262,80),(330,80),(392,80),(523,120),(659,200)]
SND_STEP_OK = [(660,80),(880,120)]
SND_DEV     = [(130,60),(174,60),(220,60),(277,60),(349,80),(440,160)]  # Konami jingle

# ── Fichiers système protégés ─────────────────────────────────────────────────
SYS_FILES = frozenset({
    "config.py","core/hw.py","core/store.py","core/net.py",
    "core/ui.py","core/web.py","boot.py","main.py",
    "core/runner.py","core/notif.py","core/accel.py",
})

# ── Catalogue des ateliers ────────────────────────────────────────────────────
# Format : (label affiché, icône core/ui.py, module apps/, ctf_id)
# ctf_id = None  →  outil non comptabilisé pour la victoire
ATELIERS = [
    ("Le Morse",     "morse",    "morse",          "morse"),
    ("Code Cesar",   "key",      "cesar",          "cesar"),
    ("Le Simon",     "bolt",     "simon",          "simon"),
    ("Le Cadenas",   "padlock",  "crochetage",     "crochetage"),
    ("Le Radar",     "signal",   "radio_dist",     "radio_dist"),
    ("Reglages",     "anchor",   "reglages",       None),
]
