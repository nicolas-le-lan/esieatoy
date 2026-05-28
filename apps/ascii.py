# =============================================================================
# apps/ascii.py — Atelier 4 : LE CODE ASCII (décodeur binaire)
# =============================================================================
# STORY : La tablette affiche un flux de données brutes binaire après avoir
#         contourné le Simon. Il faut décoder le mot secret "TOY" en binaire.
# BOUTONS :
#   LT/RT = déplacer le pointeur de bit (0 à 7)
#   UP/DN = inverser l'état du bit (0 <-> 1)
#   A     = valider le caractère actuel
#   B     = abandonner / retour menu
# =============================================================================
from core import hw, ui, store
import config as C
import time

CID = "ascii"
TARGET = ["T", "O", "Y"]
TARGET_VALS = [84, 79, 89]

_INTRO = [
    "Apres avoir bypass\nle verrou Simon,\nla tablette\naffiche un flux",
    "de donnees brutes\nen binaire !\nUne sorte de\ncle d'acces...",
    "Chaque octet de\n8 bits cache une\nlettre codee\nen ASCII !",
    "Le mot recherche\nest le suffixe de\nla tablette :\n\n  ESIEAtoy !",
    "Chaque bit vaut\nune puissance de 2\n(128, 64, ..., 1).\nLe but est de",
    "reconstituer le\nmot secret de\n3 lettres !",
    "En cas d'erreur,\ndes indices\ndetailles seront\ndisponibles !",
    "UP/DN = bit 0 / 1\nLT/RT = curseur\nA = valider lettre\nB = quitter",
]


def _val(bits):
    """Calcule la valeur décimale de l'octet (MSB à gauche)."""
    v = 0
    for i in range(8):
        if bits[i]:
            v += 1 << (7 - i)
    return v


def _char(val):
    """Retourne le caractère ASCII correspondant, ou '?' si non-imprimable."""
    if 32 <= val <= 126:
        return chr(val)
    return "?"


def _draw(letter_idx, bits, cursor):
    val = _val(bits)
    hw.oled.fill(0)
    ui.header("CODE ASCII", "%d/3" % (letter_idx + 1))

    # Dessin des 8 bits sous forme de boîtes horizontales
    # Largeur de chaque boîte : 10px, hauteur : 10px, espace : 4px
    # Largeur totale : 8 * 10 + 7 * 4 = 108px. Centrage : x = (128 - 108) // 2 = 10px
    by = 16
    for k in range(8):
        bx = 10 + k * 14
        if bits[k] == 1:
            hw.oled.fill_rect(bx, by, 10, 10, 1)
            hw.oled.text("1", bx + 1, by + 1, 0)
        else:
            ui.rrect(bx, by, 10, 10, 1)
            hw.oled.text("0", bx + 1, by + 1, 1)

    # Curseur sous la boîte active
    cx = 10 + cursor * 14 + 1
    hw.oled.text("^", cx, by + 10, 1)

    # Valeur du bit sous le curseur (POIDS) placé de manière réactive
    weight = 1 << (7 - cursor)
    w_str = "POIDS:%d" % weight
    wx = 80 if cx < 64 else 4
    hw.oled.text(w_str, wx, by + 10, 1)

    # Affichage dynamique décimal et caractère
    info_str = "DEC: %d  CHAR: %s" % (val, _char(val))
    hw.oled.text(info_str, hw.cx(info_str), by + 18, 1)

    # Progression du mot décodé
    word_str = ""
    for idx in range(3):
        if idx < letter_idx:
            word_str += TARGET[idx] + " "
        elif idx == letter_idx:
            word_str += "_ "
        else:
            word_str += ". "
    word_str = word_str.strip()
    hw.oled.text(word_str, hw.cx(word_str), by + 26, 1)

    ui.footer("Annuler", "Valider")
    hw.oled_show()


def run():
    if store.get("ctf", CID, False):
        if not ui.confirm("DEJA RESOLU", "Rejouer cet atelier ?"):
            return

    if not ui.story_pages("CODAGE ASCII", _INTRO):
        return

    letter_idx = 0
    bits = [0] * 8
    cursor = 0

    while True:
        _draw(letter_idx, bits, cursor)
        b = hw.wait_btn(0)

        if b == "b":
            return
        elif b in ("lt", "up", "dn", "rt"):
            hw.touch()
            if b == "lt":
                cursor = (cursor - 1) % 8
                hw.melody(C.SND_NAV)
            elif b == "rt":
                cursor = (cursor + 1) % 8
                hw.melody(C.SND_NAV)
            elif b in ("up", "dn"):
                bits[cursor] = 1 - bits[cursor]
                # Retour binaire sonore (aigu pour 1, grave pour 0)
                hw.tone(880 if bits[cursor] == 1 else 440, 30)
        elif b == "a":
            val = _val(bits)
            if val == TARGET_VALS[letter_idx]:
                # Lettre correcte !
                hw.melody(C.SND_STEP_OK)
                if letter_idx < 2:
                    letter_idx += 1
                    bits = [0] * 8
                    cursor = 0
                else:
                    # Tout est résolu !
                    store.put("ctf", CID, True)
                    store.save()
                    hw.led_green()
                    hw.melody(C.SND_WIN)
                    ui.story_pages("RESOLU !", [
                        "Le code 'TOY'\na devalise le\nscript d'accueil.\nLa tablette",
                        "emet un sifflement\net indique la\nposition exacte\ndu coffre !",
                        "Mais ce coffre\nest verrouille\npar un cadenas\nmecanique...",
                        "Preparez-vous a\ncrocheter sa serrure\npour en savoir\nplus !",
                    ])
                    hw.led_off()
                    ui.victory("ASCII OK", "Code decrypte !", "Atelier 4/6")
                    return
            else:
                # Lettre erronée
                hw.led_red()
                hw.melody(C.SND_ERR)
                ui.message("ERREUR", "L'octet ne donne\npas la bonne\nlettre !", 1200)
                hw.led_off()

                # Proposition d'indice
                hw.melody(C.SND_HINT)
                if ui.confirm("INDICE", "Afficher l'indice\npour la lettre\n%s ?" % TARGET[letter_idx]):
                    _show_hint(letter_idx)


def _show_hint(letter_idx):
    if letter_idx == 0:
        ui.story_pages("INDICE 1/3", [
            "Le mot secret est\nle suffixe de la\ntablette :\n\n  ESIEAtoy !",
            "La premiere lettre\nest donc le 'T'.\n\nSon code dec : 84",
            "Astuce binaire :\n84 = 64 + 16 + 4\nActive uniquement\nces 3 bits !",
        ])
    elif letter_idx == 1:
        ui.story_pages("INDICE 2/3", [
            "Le mot secret est\nle suffixe de la\ntablette :\n\n  ESIEAtoy !",
            "La deuxieme\nlettre est le 'O'.\n\nSon code dec : 79",
            "Astuce binaire :\n79 = 64 + 8\n   + 4 + 2 + 1\nActive ces bits !",
        ])
    elif letter_idx == 2:
        ui.story_pages("INDICE 3/3", [
            "Le mot secret est\nle suffixe de la\ntablette :\n\n  ESIEAtoy !",
            "La derniere\nlettre est le 'Y'.\n\nSon code dec : 89",
            "Astuce binaire :\n89 = 64 + 16\n   + 8 + 1\nActive ces bits !",
        ])
