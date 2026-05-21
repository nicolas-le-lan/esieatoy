# =============================================================================
# apps/crochetage.py — Atelier 3 : LE CADENAS (crochetage)
# =============================================================================
# STORY : Un vieux coffre en fer barre le passage. Pas de clé !
#         Il faut crocheter la serrure en manipulant 3 ressorts internes.
# BOUTONS :
#   B = annuler / retour menu
# INTERACTION :
#   Pencher la tablette gauche/droite (accéléromètre axe X) pour déplacer
#   le crochet. Trouver la bonne position pour chaque ressort et la tenir.
#   Feedback sonore et LED selon la proximité du point de blocage.
# =============================================================================
from core import hw, ui, store
import config as C
import time

CID = "crochetage"

# Positions cibles pour les 3 ressorts (0-100, axe inclinaison)
_PINS   = [25, 68, 42]
_WINDOW = 8     # tolérance ±8 unités autour du point de blocage
_HOLD   = 700   # ms à maintenir en zone pour débloquer un ressort

_INTRO = [
    "Un coffre en fer\nancien bloque\nle passage.\nPas de cle !",
    "Barbe Noire vous\nregarde et dit :\n'Je sais que tu\nsais crochet.'",
    "Penche la\ntablette gauche\nou droite pour\nmanipuler l outil.",
    "3 ressorts a\ndebloquer. Tiens\nla bonne position\njusqu au CLIC !",
]


def _tilt():
    """Retourne une position 0-100 d'après l'accéléromètre axe X."""
    try:
        from core import accel
        x, _, _ = accel.get().read()
        # ±500 unités brutes couvrent ~25° de chaque côté → 0-100
        return max(0, min(100, int((x + 500) * 100 / 1000)))
    except:
        import math
        t = time.ticks_ms() / 600.0
        return int((math.sin(t) * 0.5 + 0.5) * 100)


def _draw(pin_idx, pos, hold_ms, dist):
    hw.oled.fill(0)
    ui.header("CADENAS", "%d/3" % (pin_idx + 1))
    cy = ui.CTY() + 2

    # Indicateurs des 3 ressorts (centré)
    for i in range(3):
        sx = 32 + i * 24
        if i < pin_idx:
            ui.draw_sprite("check", sx, cy)
        elif i == pin_idx:
            ui.draw_sprite("lock", sx, cy)
        else:
            hw.oled.rect(sx, cy, 8, 8, 1)

    # Barre de position avec curseur
    bx = 4; by = cy + 12; bw = 120; bh = 7
    hw.oled.rect(bx, by, bw, bh, 1)
    cur = bx + 1 + int(pos * (bw - 4) / 100)
    hw.oled.fill_rect(cur, by + 1, 4, bh - 2, 1)

    # Statut et LED
    if dist < _WINDOW:
        status = "POSITION OK!"
        hw.led_green()
    elif dist < _WINDOW * 2:
        status = "Chaud !"
        hw.led_yellow()
    elif dist < _WINDOW * 3:
        status = "Tiede..."
        hw.led_blue()
    else:
        status = "Froid"
        hw.led_off()

    hw.oled.text(status, hw.cx(status), cy + 23, 1)

    # Barre de maintien (uniquement quand dans la zone)
    if dist < _WINDOW:
        ui.hbar(24, cy + 34, 80, 5, hold_ms, _HOLD)

    ui.footer("Annuler")
    hw.oled_show()


def _feedback_sound(dist):
    """Tick sonore dont la fréquence augmente avec la proximité."""
    if   dist < _WINDOW:     hw.tone(1200, 20)
    elif dist < _WINDOW * 2: hw.tone(750, 18)
    elif dist < _WINDOW * 3: hw.tone(420, 15)


def run():
    if store.get("ctf", CID, False):
        if not ui.confirm("DEJA RESOLU", "Rejouer ce cadenas ?"):
            return

    if not ui.story_pages("CADENAS", _INTRO):
        return

    pin_idx    = 0
    hold_start = 0
    in_zone    = False
    tick_ts    = 0

    while True:
        pos   = _tilt()
        sweet = _PINS[pin_idx]
        dist  = abs(pos - sweet)
        ok    = dist < _WINDOW

        if ok:
            if not in_zone:
                in_zone    = True
                hold_start = time.ticks_ms()
            hold_elapsed = time.ticks_diff(time.ticks_ms(), hold_start)
        else:
            in_zone      = False
            hold_elapsed = 0

        _draw(pin_idx, pos, hold_elapsed, dist)

        # Sons de feedback périodiques
        now = time.ticks_ms()
        if   dist < _WINDOW:     interval = 110
        elif dist < _WINDOW * 2: interval = 320
        elif dist < _WINDOW * 3: interval = 650
        else:                    interval = 9999
        if time.ticks_diff(now, tick_ts) >= interval:
            _feedback_sound(dist)
            tick_ts = now

        # Ressort débloqué !
        if ok and hold_elapsed >= _HOLD:
            hw.led_white()
            hw.melody(C.SND_STEP_OK)
            hw.led_off()
            pin_idx += 1
            in_zone    = False
            hold_start = 0

            if pin_idx >= len(_PINS):
                break   # tous débloqués → victoire

        b = hw.read_btn()
        if b == "b":
            hw.led_off()
            return

        time.sleep_ms(30)

    # ── Victoire ─────────────────────────────────────────────────────────────
    hw.led_green()
    hw.melody(C.SND_WIN)
    hw.oled.fill(0)
    ui.header("OUVERT !")
    hw.oled.text("CLIC CLIC CLIC!", hw.cx("CLIC CLIC CLIC!"), ui.MID() - 6, 1)
    hw.oled.text("Le coffre cede !", hw.cx("Le coffre cede !"), ui.MID() + 5, 1)
    hw.oled_show()
    time.sleep_ms(1200)
    hw.led_off()

    store.put("ctf", CID, True)
    store.save()

    ui.story_pages("OUVERT !", [
        "Le coffre grince\net s'ouvre !\nA l'interieur :\nun appareil...",
        "...avec des LED,\nune antenne et\nun message grave\ndans le metal :",
        "RADAR - Maintenir\na 50 cm de\ndistance de son\nhomologue.",
        "Ce n'est pas un\njouet du passe.\nCes objets\nviennent du futur!",
    ])
    ui.victory("CADENAS OK", "Coffre ouvert !", "Atelier 3/4")
