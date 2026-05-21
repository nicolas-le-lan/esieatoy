# =============================================================================
# apps/cesar.py — Atelier 2 : LE CODAGE (chiffre de César)
# =============================================================================
# STORY : Un message chiffré apparaît sur la tablette.
#         Chaque lettre a été décalée d'un même nombre de crans dans l'alphabet.
#         Message en clair : "DEUX MILLE VINGT SIX" → 2026 !
# BOUTONS :
#   UP/DN  = décalage ±1
#   LT/RT  = décalage ±5
#   A      = valider quand le texte est lisible
#   B      = annuler / retour menu
# =============================================================================
from core import hw, ui, store
import config as C

CID    = "cesar"
ALPHA  = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_SHIFT = 10

# Cipher généré avec shift +10 sur "DEUX MILLE VINGT SIX"
_CIPHER = "NOEH WSVVO FSXQD CSH"
_PLAIN  = "DEUX MILLE VINGT SIX"

_INTRO = [
    "Un message est\napparu sur\nl'ecran, mais\nles lettres sont",
    "...toutes fausses.\nC'est le CODE\nDE CESAR !\nChaque lettre est",
    "remplacee par\nune autre, a une\ncertaine distance\ndans l alphabet.",
    "UP/DN = +/-1\nLT/RT = +/-5\nA = valider\nB = annuler",
]


def _decode(cipher, shift):
    result = []
    for ch in cipher:
        if ch in ALPHA:
            result.append(ALPHA[(ALPHA.find(ch) - shift) % 26])
        else:
            result.append(ch)
    return "".join(result)


def _draw(shift):
    plain   = _decode(_CIPHER, shift)
    c_lines = ui.wrap(_CIPHER, 14)
    d_line  = ui.wrap(plain, 15)[0]

    hw.oled.fill(0)
    ui.header("CODAGE", "CESAR")

    # Message chiffré sur fond inversé (2 lignes max)
    for i, ln in enumerate(c_lines[:2]):
        y = 14 + i * 10
        hw.oled.fill_rect(0, y, hw.W, 9, 1)
        hw.oled.text(ln, hw.cx(ln), y + 1, 0)

    # Décalage courant (centré)
    s_str = "< +%d >" % shift
    hw.oled.text(s_str, hw.cx(s_str), 34, 1)

    # Aperçu du décodage (première ligne)
    hw.oled.text(d_line, hw.cx(d_line), 43, 1)

    ui.footer("Annuler", "Valider")
    hw.oled_show()


def run():
    if store.get("ctf", CID, False):
        if not ui.confirm("DEJA RESOLU", "Rejouer cet atelier ?"):
            return

    if not ui.story_pages("CODAGE", _INTRO):
        return

    shift = 0

    while True:
        _draw(shift)
        b = hw.wait_btn(150)

        if b is None:
            continue
        elif b == "b":
            return
        elif b == "up":
            shift = (shift + 1) % 26
            hw.melody(C.SND_NAV)
        elif b == "dn":
            shift = (shift - 1) % 26
            hw.melody(C.SND_NAV)
        elif b == "rt":
            shift = (shift + 5) % 26
            hw.melody(C.SND_NAV)
        elif b == "lt":
            shift = (shift - 5) % 26
            hw.melody(C.SND_NAV)
        elif b == "a":
            if _decode(_CIPHER, shift).strip() == _PLAIN.strip():
                store.put("ctf", CID, True)
                store.save()
                hw.melody(C.SND_WIN)
                hw.led_green()
                ui.story_pages("DECOUVERT !", [
                    "Le message\nrevele une date\nmysterieuse !",
                    "Comment un objet\ntrouve en 1700\npeut contenir\ncette date ?",
                    "Vous comprenez...\nces tablettes\nviennent DU FUTUR.",
                    "Mais comment sont\nelles arrivees la ?\nEt pourquoi ?",
                ])
                hw.led_off()
                ui.victory("CODAGE OK", "Message decode !", "Atelier 2/4")
                return
            else:
                hw.melody(C.SND_ERR)
                hw.led_red()
                ui.message("NON", "Le texte n'est\npas lisible...", 900)
                hw.led_off()
