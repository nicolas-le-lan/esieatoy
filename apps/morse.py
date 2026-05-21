# =============================================================================
# apps/morse.py — Atelier 1 : LA RADIO (décodage Morse)
# =============================================================================
# STORY : La tablette émet une suite de points et de traits.
#         Le joueur écoute et tente de décoder le message caché.
# BOUTONS :
#   B / directionnel = réémettre le signal
#   A                = saisir sa réponse
# =============================================================================
from core import hw, ui, store
import config as C
import time

CID    = "morse"
TARGET = "LYS"

DOT  = 120; DASH = 320; GAP = 70; LETTER_GAP = 240

CODE = {
    "L": ".-..",
    "Y": "-.--",
    "S": "...",
    "A": ".-",
    "E": ".",
    "H": "....",
    "R": ".-.",
    "T": "-",
    "I": "..",
    "N": "-.",
}

_INTRO = [
    "La tablette\nemet une suite\nde sons courts\net longs.",
    "C est du CODE\nMORSE !\nCourt = point (.)\nLong  = tiret (-)",
    "Chaque lettre\ncorrespond a une\nsequence unique.\nTrouve le mot !",
    "B = reecouter\nA = saisir\nta reponse",
]


def _emit_morse():
    for ch in TARGET:
        for sym in CODE[ch]:
            hw.led_white()
            hw.tone(820, DOT if sym == "." else DASH)
            hw.led_off()
            time.sleep_ms(GAP)
        time.sleep_ms(LETTER_GAP)


def _draw_idle(tick):
    hw.oled.fill(0)
    ui.header("RADIO", "MORSE")
    cy = ui.CTY() + 2
    cx = hw.W // 2
    for i, r in enumerate([5, 11, 17, 23]):
        if ((tick + i * 3) % 8) < 4:
            hw.oled.ellipse(cx, cy + 12, r, r, 1)
    hw.oled.text("Signal capte !", hw.cx("Signal capte !"), cy + 29, 1)
    ui.footer("Repeter", "Saisir")
    hw.oled_show()


def _draw_emitting(tick):
    hw.oled.fill(0)
    ui.header("RADIO", "EMIT")
    cy = ui.CTY() + 2
    cx = hw.W // 2
    for i, r in enumerate([6, 12, 18, 24]):
        if ((tick + i * 2) % 6) < 3:
            hw.oled.ellipse(cx, cy + 12, r, r, 1)
    hw.oled.text("EMISSION...", hw.cx("EMISSION..."), cy + 29, 1)
    hw.oled_show()


def run():
    if store.get("ctf", CID, False):
        if not ui.confirm("DEJA RESOLU", "Rejouer cet atelier ?"):
            return

    if not ui.story_pages("RADIO", _INTRO):
        return

    hw.oled.fill(0)
    ui.header("RADIO", "EMIT")
    hw.oled.text("EMISSION...", hw.cx("EMISSION..."), ui.MID() - 4, 1)
    hw.oled_show()
    _emit_morse()

    tick = 0

    while True:
        _draw_idle(tick)
        b = hw.wait_btn(180)
        tick = (tick + 1) % 32

        if b in ("b", "lt", "dn", "rt", "up"):
            for t in range(10):
                _draw_emitting(t * 2)
                time.sleep_ms(30)
            _emit_morse()

        elif b == "a":
            guess = ui.input_text("MOT DECODE", "", 3,
                                   "ABCDEFGHIJKLMNOPQRSTUVWXYZ")
            if not guess.strip():
                continue  # annulé sans rien taper
            if guess.upper().strip() == TARGET:
                store.put("ctf", CID, True)
                store.save()
                hw.melody(C.SND_WIN)
                hw.led_green()
                ui.story_pages("DECOUVERT !", [
                    "Le signal morse\netait un mot\ncache depuis\ndes siecles !",
                    "FLEUR DE LYS !\nC est un symbole\nroyal francais !",
                    "Ces objets ont\ndonc un lien avec\nla France...",
                    "Mais cela n\nexplique pas leur\norigine !",
                ])
                hw.led_off()
                ui.victory("RADIO OK", "Morse decode !", "Atelier 1/4")
                return
            else:
                hw.melody(C.SND_ERR)
                hw.led_red()
                ui.message("NON", "Ecoute bien\nchaque bip !", 1200)
                hw.led_off()
                _emit_morse()
