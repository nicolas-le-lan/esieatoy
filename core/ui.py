# =============================================================================
# core/ui.py — Interface utilisateur OLED 128×64 — Badge ESE
# =============================================================================
# Police MicroPython : 8×8 px → 16 colonnes × 8 lignes max
# Layout vertical :
#   px  0..12  → header (fond blanc, texte noir)
#   px 13      → séparateur
#   px 14..51  → zone de contenu (38px utiles)
#   px 52      → séparateur footer
#   px 53..63  → footer (boutons A / B)
# =============================================================================
from core import hw, store
import config as C
import time

try:
    import random
    random.randint(0, 1)
except:
    from core import rand as random

# ── Constantes de layout ──────────────────────────────────────────────────────
HDR_H     = 13
FTR_H     = 12
CONTENT_Y = 14

def CTY(): return CONTENT_Y
def MID(): return hw.H // 2


# ── Icônes 16×16 px (entier 16 bits, MSB = pixel gauche) ─────────────────────
ICONS = {
    # Ondes radio concentriques (atelier Morse)
    "signal": [0x0180,0x0660,0x1818,0x2004,0x4002,0x0180,0x0660,0x0180,
               0x0180,0x0000,0x0000,0x0180,0x03C0,0x03C0,0x0180,0x0000],
    # Point-trait-point (symbole Morse)
    "morse":  [0x0000,0x0000,0x3C3C,0x3C3C,0x0000,0x7FFE,0x7FFE,0x0000,
               0x0000,0x3C3C,0x3C3C,0x0000,0x7FFE,0x7FFE,0x0000,0x0000],
    # Roue à chiffres / cadenas (atelier César)
    "key":    [0x07E0,0x0FF0,0x1818,0x1818,0x0FF0,0x07E0,0x03C0,0x03C0,
               0x07E0,0x07E0,0x0660,0x07E0,0x07E0,0x0000,0x0000,0x0000],
    # Bouclier (défense / cyber)
    "shield": [0x0FF0,0x1FF8,0x3FFC,0x7FFE,0x7FFE,0x7FFE,0x7FFE,0x3FFC,
               0x3FFC,0x1FF8,0x0FF0,0x07E0,0x03C0,0x0180,0x0000,0x0000],
    # Éclair (énergie)
    "bolt":   [0x03E0,0x07C0,0x0F80,0x1F00,0x3FFE,0x1FF8,0x03F0,0x07E0,
               0x0FC0,0x1F80,0x3F00,0x7E00,0x0000,0x0000,0x0000,0x0000],
    # Tête de mort (logo principal ESIEA TOY)
    "logo":   [0x0000,0x07C0,0x1FF0,0x3FF8,0x36D8,0x3FF8,0x1FF0,0x0FF0,
               0x0FF0,0x1998,0x0FF0,0x07E0,0x03C0,0x01C0,0x0000,0x0000],
    # Crâne simplifié (utilisé dans les animations)
    "skull":  [0x0000,0x07C0,0x0FE0,0x1DB0,0x1FF0,0x1DB0,0x0FE0,0x07C0,
               0x07C0,0x0360,0x03C0,0x01C0,0x0000,0x0000,0x0000,0x0000],
    # Ancre marine
    "anchor": [0x0180,0x0180,0x7FFE,0x0180,0x0180,0x0DB6,0x1FF8,0x3FFC,
               0x318C,0x318C,0x1998,0x0FF0,0x07E0,0x03C0,0x0180,0x0000],
    # Voilier
    "ship":   [0x0100,0x0380,0x07C0,0x0FE0,0x1FF0,0x3FF8,0x3FF8,0x7FFC,
               0x3FF8,0x1FF0,0x0FE0,0x07C0,0x0380,0x0100,0x0000,0x0000],
    # Coffre au trésor
    "chest":  [0x0000,0x3FF8,0x4004,0x4FF4,0x4004,0x7FFE,0x8001,0x8181,
               0x8001,0x8001,0x8181,0x8001,0x7FFE,0x0000,0x0000,0x0000],
    # Cadenas (crochetage)
    "padlock":[0x0000,0x0FF0,0x0C30,0x0C30,0x0C30,0x0C30,0x3FFC,0x3FFC,
               0x3E7C,0x3C3C,0x3E7C,0x3FFC,0x3FFC,0x1FF8,0x0FF0,0x0000],
    # Tablette ESIEA TOY — logo principal (épuré, style device)
    # Corps arrondi 12×13 px, 3 points caméra, écran centré, bouton home
    "esiea":  [0x0000,0x1FF8,0x2004,0x2494,0x2004,0x27F4,0x27F4,0x27F4,
               0x27F4,0x27F4,0x2004,0x23C4,0x2004,0x1FF8,0x0000,0x0000],
}

# ── Sprites 8×8 px (octet, MSB = pixel gauche) ───────────────────────────────
SPRITES = {
    "face":     [0x3C,0x42,0xA5,0x81,0x81,0xBD,0x42,0x3C],
    "face_win": [0x3C,0x42,0xA5,0x81,0xBD,0x99,0x42,0x3C],
    "face_sad": [0x3C,0x42,0xA5,0x81,0x99,0xBD,0x42,0x3C],
    "star":     [0x08,0x1C,0x7F,0x1C,0x2A,0x08,0x14,0x22],
    "check":    [0x00,0x01,0x03,0x87,0xCE,0x7C,0x38,0x00],
    "cross":    [0x00,0x42,0x24,0x18,0x18,0x24,0x42,0x00],
    "lock":     [0x18,0x24,0x24,0xFF,0xFF,0xE7,0xFF,0xFF],
    "anchor":   [0x18,0x18,0xFF,0x5A,0x5A,0x3C,0x3C,0xFF],
    "wave":     [0x00,0x24,0x42,0x81,0x81,0x42,0x24,0x00],
    "skull8":   [0x3C,0x7E,0xDB,0xFF,0xFF,0xDB,0x42,0x3C],
}


# ── Primitives de dessin ──────────────────────────────────────────────────────

def draw_icon(name, x, y, c=1):
    """Affiche une icône 16×16 px à la position (x, y)."""
    data = ICONS.get(name)
    if not data: return
    for row_idx, row in enumerate(data):
        for bit in range(16):
            if row & (1 << (15 - bit)):
                hw.oled.pixel(x + bit, y + row_idx, c)

def draw_sprite(name, x, y, c=1):
    """Affiche un sprite 8×8 px à la position (x, y)."""
    data = SPRITES.get(name)
    if not data: return
    for row_idx, row in enumerate(data):
        for bit in range(8):
            if row & (0x80 >> bit):
                hw.oled.pixel(x + bit, y + row_idx, c)

def rrect(x, y, w, h, c=1):
    """Rectangle à coins arrondis d'1 pixel."""
    hw.oled.hline(x + 1, y,         w - 2, c)
    hw.oled.hline(x + 1, y + h - 1, w - 2, c)
    hw.oled.vline(x,         y + 1, h - 2, c)
    hw.oled.vline(x + w - 1, y + 1, h - 2, c)

def hbar(x, y, w, h, val, maxval, c=1):
    """Barre de progression horizontale avec bordure arrondie."""
    rrect(x, y, w, h, c)
    fill = int((w - 4) * max(0, min(val, maxval)) / max(1, maxval))
    if fill > 0:
        hw.oled.fill_rect(x + 2, y + 2, fill, h - 4, c)


# ── Helpers texte ─────────────────────────────────────────────────────────────

def _ascii(text):
    """Remplace les caractères accentués par leur base ASCII."""
    MAP = {
        'é':'e','è':'e','ê':'e','ë':'e','à':'a','â':'a','ä':'a',
        'î':'i','ï':'i','ô':'o','ö':'o','û':'u','ù':'u','ü':'u',
        'ç':'c','É':'E','È':'E','Ê':'E','À':'A','Â':'A','Ç':'C',
        'Ô':'O','Î':'I','Û':'U',
    }
    result = []
    for ch in str(text):
        if ord(ch) < 128:
            result.append(ch)
        else:
            result.append(MAP.get(ch, '?'))
    return "".join(result)

def clean(text):
    """Normalise un texte pour l'affichage OLED."""
    return _ascii(str(text).replace("\n", " ").replace("\r", " ").strip())

def wrap(text, width=15):
    """
    Découpe un texte en lignes de `width` caractères max.
    Respecte les sauts de ligne explicites (\n).
    """
    result = []
    for raw_line in _ascii(str(text)).split("\n"):
        if not raw_line:
            result.append("")
            continue
        words = raw_line.split(" ")
        line  = ""
        for word in words:
            if len(line) + len(word) + (1 if line else 0) <= width:
                line = (line + " " + word).strip() if line else word
            else:
                if line: result.append(line)
                line = word[:width]
        if line: result.append(line)
    return result or [""]

def scroll_label(text, max_chars, token=None):
    """
    Texte défilant automatiquement.
    token = time.ticks_ms() // vitesse, cyclique.
    """
    text = clean(text)
    if len(text) <= max_chars:
        return text
    if token is None:
        token = time.ticks_ms() // 160
    diff  = len(text) - max_chars
    cycle = diff * 2 + 8
    pos   = token % cycle
    if   pos < 4:           off = 0
    elif pos < 4 + diff:    off = pos - 4
    elif pos < 8 + diff:    off = diff
    else:                   off = diff - (pos - (8 + diff))
    return text[off : off + max_chars]


# ── Chrome (Header / Footer) ──────────────────────────────────────────────────

def header(title, sub=""):
    """
    Barre de titre : fond blanc, texte noir (style inversé).
    sub = texte court affiché à droite (ex: "3/5").
    Si sub est vide, une icône batterie miniature est dessinée.
    """
    hw.oled.fill_rect(0, 0, hw.W, HDR_H - 1, 1)
    hw.oled.hline(0, HDR_H - 1, hw.W, 1)
    max_c = 10 if sub else 14
    t = clean(title)
    disp = scroll_label(t, max_c) if len(t) > max_c else t
    hw.oled.text(disp, 3, 2, 0)
    if sub:
        s = clean(sub)[:5]
        hw.oled.text(s, hw.W - len(s) * 8 - 3, 2, 0)
    else:
        # Icône batterie 11×6 px (coin droit)
        bx = hw.W - 14; by = 3
        hw.oled.rect(bx, by, 11, 6, 0)
        hw.oled.fill_rect(bx + 11, by + 2, 2, 2, 0)
        if not hw.on_battery():
            hw.oled.fill_rect(bx + 1, by + 1, 9, 4, 0)   # USB = pleine
        else:
            pct = hw.get_battery_percent()
            lvl = max(1, int(pct * 9 / 100))
            hw.oled.fill_rect(bx + 1, by + 1, lvl, 4, 0)
        
        # Icône Wi-Fi — seulement en mode USB (évite le check réseau en mode batterie)
        if store.get("sys", "pwr_mode", "bat") != "bat":
            try:
                import network
                if network.WLAN(network.AP_IF).active() or network.WLAN(network.STA_IF).isconnected():
                    wx = bx - 11; wy = 3
                    hw.oled.hline(wx+2, wy, 5, 0)
                    hw.oled.pixel(wx+1, wy+1, 0); hw.oled.pixel(wx+7, wy+1, 0)
                    hw.oled.hline(wx+3, wy+2, 3, 0)
                    hw.oled.pixel(wx+2, wy+3, 0); hw.oled.pixel(wx+6, wy+3, 0)
                    hw.oled.pixel(wx+4, wy+5, 0)
            except:
                pass

def footer(left="", right=None):
    """
    Barre de pied de page avec 1 ou 2 boutons-labels.
    Un seul argument → bouton centré (action principale).
    Deux arguments   → gauche=secondaire (outline), droite=primaire (rempli).
    """
    fy = hw.H - FTR_H
    hw.oled.fill_rect(0, fy, hw.W, FTR_H, 0)
    hw.oled.hline(0, fy, hw.W, 1)

    if right is None:
        # Bouton unique centré
        t = clean(left)[:14]
        if not t: return
        tw = len(t) * 8 + 8
        tx = (hw.W - tw) // 2
        hw.oled.fill_rect(tx, fy + 2, tw, 9, 1)
        hw.oled.text(t, tx + 4, fy + 3, 0)
        return

    # Bouton gauche : outline (secondaire)
    lt = clean(left)[:6]
    if lt:
        lw = len(lt) * 8 + 8
        rrect(2, fy + 2, lw, 9, 1)
        hw.oled.text(lt, 6, fy + 3, 1)

    # Bouton droit : rempli (primaire)
    rt = clean(right)[:6]
    if rt:
        rw = len(rt) * 8 + 8
        rx = hw.W - rw - 2
        hw.oled.fill_rect(rx, fy + 2, rw, 9, 1)
        hw.oled.text(rt, rx + 4, fy + 3, 0)


# ── Composants ────────────────────────────────────────────────────────────────

def message(title, body, delay_ms=None):
    """
    Message plein écran, corps multi-lignes (jusqu'à 3).
    delay_ms=None → attente bouton A/B.
    delay_ms=N    → auto-dismiss après N ms (appui bouton accélère).
    """
    lines = wrap(body, 15)[:3]
    n     = len(lines)
    zone  = hw.H - HDR_H - FTR_H
    total = (n - 1) * 10 + 8
    cy    = HDR_H + (zone - total) // 2
    t0    = time.ticks_ms()
    while True:
        hw.oled.fill(0)
        header(title)
        for i, ln in enumerate(lines):
            hw.oled.text(ln, hw.cx(ln), cy + i * 10, 1)
        if delay_ms is None:
            footer("Retour", "OK")
        hw.oled_show()
        if delay_ms is not None:
            if time.ticks_diff(time.ticks_ms(), t0) >= delay_ms: return
            if hw.read_btn(): return
            time.sleep_ms(35)
        else:
            b = hw.wait_btn(0)
            return "a" if b == "a" else "b"

def scroll_text(title, text):
    """Affichage scrollable pour les textes longs (notices, narratif)."""
    lines = wrap(text, 15)
    lines.append("")   # marge de fin
    pos = 0
    vis = 4   # lignes visibles simultanément

    while True:
        hw.oled.fill(0)
        header(title)
        cy = CTY() + 2
        for i in range(vis):
            if pos + i < len(lines):
                hw.oled.text(lines[pos + i], 4, cy + i * 9, 1)
        # Scrollbar verticale
        if len(lines) > vis:
            bh = max(4, (hw.H - HDR_H - FTR_H) * vis // len(lines))
            max_scroll = len(lines) - vis
            by = CTY() + 2 + (hw.H - HDR_H - FTR_H - bh) * pos // max(1, max_scroll)
            hw.oled.fill_rect(hw.W - 3, by, 3, bh, 1)
        footer("Retour", "OK")
        hw.oled_show()
        b = hw.wait_btn(0)
        if b == "b": return "b"
        elif b == "a": return "a"
        elif b in ("up", "lt") and pos > 0:
            pos -= 1; hw.melody(C.SND_NAV)
        elif b in ("dn", "rt") and pos < len(lines) - vis:
            pos += 1; hw.melody(C.SND_NAV)

def confirm(title, body):
    """
    Dialog de confirmation OUI / NON.
    Retourne True si l'utilisateur choisit OUI.
    """
    sel = 0
    hw.melody(C.SND_TICK)
    while True:
        hw.oled.fill(0)
        header(title)
        for i, line in enumerate(wrap(body, 15)[:3]):
            hw.oled.text(line, hw.cx(line), CTY() + 2 + i * 10, 1)
        fy = hw.H - FTR_H
        hw.oled.hline(0, fy, hw.W, 1)
        bw = 52; by = fy + 2; bh = 9
        for i, lbl in enumerate(("OUI", "NON")):
            x = 4 if i == 0 else hw.W - bw - 4
            if sel == i:
                hw.oled.fill_rect(x, by, bw, bh, 1)
                hw.oled.text(lbl, x + (bw - 24) // 2, by + 1, 0)
            else:
                rrect(x, by, bw, bh, 1)
                hw.oled.text(lbl, x + (bw - 24) // 2, by + 1, 1)
        hw.oled_show()
        b = hw.wait_btn(0)
        if b in ("lt", "rt", "up", "dn"):
            sel = 1 - sel; hw.melody(C.SND_NAV)
        elif b == "a":
            hw.melody(C.SND_OK); return sel == 0
        elif b == "b":
            return False

def story_pages(title, pages):
    """
    Navigation multi-pages avec scroll intra-page si le texte dépasse 4 lignes.
    A/RT/DN = avancer (ligne ou page). B/LT/UP = reculer. Retourne True/False.
    """
    n   = len(pages)
    pg  = 0   # index de page
    lp  = 0   # décalage de scroll dans la page courante
    VIS = 4

    while True:
        lines   = wrap(pages[pg], 15)
        at_end  = lp + VIS >= len(lines)
        at_top  = lp == 0

        hw.oled.fill(0)
        header(title, "%d/%d" % (pg + 1, n))
        cy = CTY() + 2
        for i in range(VIS):
            li = lp + i
            if li < len(lines):
                hw.oled.text(lines[li], 4, cy + i * 9, 1)

        # Scrollbar verticale si overflow
        if len(lines) > VIS:
            bh = max(4, (hw.H - HDR_H - FTR_H) * VIS // len(lines))
            ms = max(1, len(lines) - VIS)
            by = CTY() + 2 + (hw.H - HDR_H - FTR_H - bh) * lp // ms
            hw.oled.fill_rect(hw.W - 3, by, 3, bh, 1)

        # Footer adaptatif
        last_page = pg == n - 1
        first_page = pg == 0
        if first_page and at_top and last_page and at_end:
            footer("Quitter", "OK")
        elif last_page and at_end:
            footer("Retour", "OK")
        elif first_page and at_top:
            footer("Quitter", "Suite")
        else:
            footer("Retour", "Suite")

        hw.oled_show()
        b = hw.wait_btn(0)

        if b in ("a", "rt", "dn"):
            if not at_end:
                lp += 1
                hw.melody(C.SND_NAV)
            elif pg < n - 1:
                pg += 1; lp = 0
                hw.melody(C.SND_NAV)
            else:
                return True
        elif b in ("b", "lt", "up"):
            if not at_top:
                lp -= 1
                hw.melody(C.SND_NAV)
            elif pg > 0:
                pg -= 1
                prev = wrap(pages[pg], 15)
                lp = max(0, len(prev) - VIS)
                hw.melody(C.SND_NAV)
            else:
                return False

def input_text(title, default="", max_len=6,
               charset="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 "):
    """
    Saisie caractère par caractère.
    UP/DN = changer lettre courante.
    A     = confirmer la lettre et avancer (sur le dernier slot → étape de validation).
    LT    = effacer la lettre précédente.
    RT    = avancer sans insérer.
    B     = annuler (retourne "" quelle que soit la saisie).
    Étape finale : A = soumettre, B/LT = revenir corriger.
    """
    chars = list(charset)
    buf   = list(default.upper()[:max_len])
    pos   = len(buf)
    ci    = 0

    while True:
        hw.oled.fill(0)
        header(title)
        cy = CTY() + 4

        s = "".join(buf)
        display = (s + "_" * (max_len - len(s)))[:max_len]
        dx = hw.cx(display)
        hw.oled.text(display, dx, cy, 1)

        if pos < max_len:
            # Mode saisie : curseur + sélecteur de lettre
            hw.oled.hline(dx + pos * 8, cy + 9, 8, 1)
            cw = "[" + chars[ci % len(chars)] + "]"
            hw.oled.text(cw, hw.cx(cw), cy + 16, 1)
            lbl = "Valider" if pos == max_len - 1 else "Saisir"
            footer("Effacer", lbl)
        else:
            # Mode confirmation : tous les slots remplis
            ok_lbl = "[ OK ? ]"
            hw.oled.text(ok_lbl, hw.cx(ok_lbl), cy + 16, 1)
            footer("Corriger", "Valider")

        hw.oled_show()
        b = hw.wait_btn(0)

        if pos == max_len:
            # Confirmation finale
            if b == "a":
                return "".join(buf)
            elif b in ("b", "lt"):
                pos = max_len - 1   # revenir corriger le dernier slot
            continue

        # Mode saisie normale
        if b == "up":
            ci = (ci - 1) % len(chars)
            hw.melody(C.SND_NAV)
        elif b == "dn":
            ci = (ci + 1) % len(chars)
            hw.melody(C.SND_NAV)
        elif b == "a":
            c = chars[ci % len(chars)]
            if pos < len(buf):
                buf[pos] = c
            elif len(buf) < max_len:
                buf.append(c)
            hw.melody(C.SND_TICK)
            pos += 1   # avance ; si pos == max_len → mode confirmation
            ci = 0
        elif b == "rt":
            if pos < len(buf):
                pos += 1
            hw.melody(C.SND_NAV)
        elif b == "lt":
            if pos > 0:
                buf = buf[:pos - 1] + buf[pos:]
                pos = max(0, pos - 1)
                ci = 0
                hw.melody(C.SND_NAV)
        elif b == "b":
            return ""   # annulation propre — toujours vide

def shake(ms=300):
    """Effet d'erreur visuel : clignotement rapide de l'écran + LED rouge."""
    steps = max(2, ms // 60)
    for i in range(steps):
        hw.oled.fill(1 if i % 2 else 0)
        hw.oled_show()
        hw.led_red() if i % 2 else hw.led_off()
        time.sleep_ms(60)
    hw.oled.fill(0)
    hw.led_off()

def victory(title, line1, line2):
    """
    Écran de victoire animé : bordures clignotantes, étoiles aléatoires,
    face souriante, LEDs colorées.
    """
    hw.led_green()
    hw.melody(C.SND_WIN)
    t1 = clean(line1)[:14]
    t2 = clean(line2)[:14]

    for frame in range(28):
        hw.oled.fill(0)
        # LEDs tournantes
        [hw.led_green, hw.led_blue, hw.led_cyan][frame % 3]()
        # Bordure clignotante
        brd = frame % 2
        hw.oled.rect(brd, brd, hw.W - brd * 2, hw.H - brd * 2, 1)
        # Étoiles aléatoires
        for _ in range(5):
            draw_sprite("star",
                        random.randint(4,  hw.W - 12),
                        random.randint(14, hw.H - 20))
        # Face + texte
        draw_sprite("face_win", hw.cx("") - 4, 14)
        hw.oled.text(t1, hw.cx(t1), 26, 1)
        hw.oled.text(t2, hw.cx(t2), 36, 1)
        footer("Menu", "OK")
        hw.oled_show()
        time.sleep_ms(90)
        if frame > 8 and hw.read_btn():
            break

    hw.led_off()
    hw.wait_btn(1500)

def run_menu(title, items, on_sel, status=None):
    """
    Menu liste déroulante.
    items   = liste de str.
    on_sel  = callback(idx) → retourner False pour fermer le menu.
    UP/DN   = naviguer. A = sélectionner. B = fermer.
    """
    sel = 0
    n   = len(items)
    VIS = 4

    while True:
        start = max(0, min(sel - 1, n - VIS))
        hw.oled.fill(0)
        header(title)
        for i in range(VIS):
            idx = start + i
            if idx >= n:
                break
            y = CTY() + i * 10
            lbl = clean(items[idx])[:14]
            if idx == sel:
                hw.oled.fill_rect(0, y, hw.W, 9, 1)
                hw.oled.text(lbl, 2, y + 1, 0)
            else:
                hw.oled.text(lbl, 2, y + 1, 1)

        # Indicateurs de scroll
        if start > 0:
            hw.oled.text("^", hw.W - 9, CTY(), 1)
        if start + VIS < n:
            hw.oled.text("v", hw.W - 9, CTY() + (VIS - 1) * 10, 1)

        footer("Retour", "OK")
        hw.oled_show()

        b = hw.wait_btn(0)
        if b in ("up", "lt"):
            sel = (sel - 1) % n
            hw.melody(C.SND_NAV)
        elif b in ("dn", "rt"):
            sel = (sel + 1) % n
            hw.melody(C.SND_NAV)
        elif b == "a":
            hw.melody(C.SND_TICK)
            result = on_sel(sel)
            if result is False:
                return sel
        elif b == "b":
            return None


def toggle(title, label, current):
    """
    Bascule ON/OFF. Retourne la nouvelle valeur ou None si annulé (B).
    LT/RT/UP/DN = basculer. A = confirmer. B = annuler.
    """
    val = current
    while True:
        hw.oled.fill(0)
        header(title)
        cy = CTY() + 4
        lbl = clean(label)[:14]
        hw.oled.text(lbl, hw.cx(lbl), cy, 1)

        state = "ON " if val else "OFF"
        sw = len(state) * 8 + 16
        sx = (hw.W - sw) // 2
        sy = cy + 18
        if val:
            hw.oled.fill_rect(sx, sy, sw, 13, 1)
            hw.oled.text(state, sx + 8, sy + 3, 0)
        else:
            rrect(sx, sy, sw, 13, 1)
            hw.oled.text(state, sx + 8, sy + 3, 1)

        footer("Annuler", "OK")
        hw.oled_show()

        b = hw.wait_btn(0)
        if b in ("lt", "rt", "up", "dn"):
            val = not val
            hw.melody(C.SND_NAV)
        elif b == "a":
            hw.melody(C.SND_OK)
            return val
        elif b == "b":
            return None


def validate_answer(title, correct, length=None):
    """
    Saisie d'une réponse + validation. Retourne True si correct, False si annulé.
    Gère les mauvaises réponses en boucle jusqu'à succès ou abandon (B vide).
    """
    correct_clean = correct.upper().strip()
    n = length or len(correct_clean)
    while True:
        guess = input_text(title, "", n, "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 ")
        if not guess.strip():
            return False   # annulé (B sans rien taper)
        if guess.upper().strip() == correct_clean:
            return True
        hw.melody(C.SND_ERR)
        hw.led_red()
        hw.oled.fill(0)
        header("RATÉ")
        cy = CTY() + 8
        hw.oled.text("Mauvaise reponse", hw.cx("Mauvaise reponse"), cy, 1)
        hw.oled.text("Essaie encore !", hw.cx("Essaie encore !"), cy + 12, 1)
        footer("Quitter", "Reessayer")
        hw.oled_show()
        time.sleep_ms(150)
        hw.led_off()
        b = hw.wait_btn(4000)
        if b == "b":
            return False


def crash_screen(err_msg):
    """Écran d'erreur critique affiché en cas d'exception non catchée."""
    hw.led_red()
    try:
        hw.melody(C.SND_ERR)
    except:
        pass
    hw.oled.fill(0)
    hw.oled.fill_rect(0, 0, hw.W, 13, 1)
    hw.oled.text("!! ERREUR !!", hw.cx("!! ERREUR !!"), 2, 0)
    for i, line in enumerate(wrap(str(err_msg), 15)[:4]):
        hw.oled.text(line, 0, 14 + i * 10, 1)
    hw.oled.text("B = retour menu", 0, 55, 1)
    hw.oled_show()
    hw.wait_btn(8000)
    hw.led_off()
