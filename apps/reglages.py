# =============================================================================
# apps/reglages.py — Paramètres système ESIEAtoy
# =============================================================================
from core import hw, ui, store
import config as C
import time


# ═══════════════════════════════════════════════════════════════════════════════
# CONNEXION — sous-menu + écrans
# ═══════════════════════════════════════════════════════════════════════════════

def _screen_hotspot():
    """SSID + MDP en grandes boites inversées. A = toggle AP."""
    from core import net as NET

    def _ap_state():
        try:
            import network
            ap = network.WLAN(network.AP_IF)
            ip = ap.ifconfig()[0] if ap.active() else C.AP_IP
            return ap.active(), ip
        except:
            return False, C.AP_IP

    ssid = store.get("wifi", "ap_ssid") or NET.default_ssid()
    pwd  = store.get("wifi", "ap_pwd")  or NET.default_pwd()

    while True:
        ap_on, ip = _ap_state()

        hw.oled.fill(0)
        ui.header("HOTSPOT", "ON" if ap_on else "OFF")
        cy = ui.CTY()   # 14

        # ── SSID ──────────────────────────────────────────────────────────────
        hw.oled.text("SSID", 2, cy, 1)
        ssid_d = ssid[:15]
        hw.oled.fill_rect(0, cy + 9, C.W, 10, 1)
        hw.oled.text(ssid_d, max(0, (C.W - len(ssid_d) * 8) // 2), cy + 10, 0)

        # ── MDP ───────────────────────────────────────────────────────────────
        hw.oled.text("MDP", 2, cy + 21, 1)
        pwd_d = pwd[:15]
        hw.oled.fill_rect(0, cy + 30, C.W, 10, 1)
        hw.oled.text(pwd_d, max(0, (C.W - len(pwd_d) * 8) // 2), cy + 31, 0)

        act = "Stopper" if ap_on else "Activer"
        ui.footer("Retour", act)
        hw.oled_show()

        b = hw.wait_btn(0)
        if b == "b":
            return
        elif b == "a":
            try:
                if ap_on:
                    NET.ap_stop()
                    hw.melody(C.SND_ERR)
                else:
                    NET.ap_start()
                    ssid = store.get("wifi", "ap_ssid") or NET.default_ssid()
                    pwd  = store.get("wifi", "ap_pwd")  or NET.default_pwd()
                    hw.melody(C.SND_OK)
            except Exception as ex:
                ui.message("ERREUR", str(ex)[:15], 2000)


def _screen_wifi():
    """Scan WiFi + connexion STA."""
    from core import net as NET
    try:
        import network
    except:
        ui.message("ERREUR", "WiFi indisponible", 2000)
        return

    sta = network.WLAN(network.STA_IF)

    # ── Scan ──────────────────────────────────────────────────────────────────
    hw.oled.fill(0)
    ui.header("WIFI")
    hw.oled.text("Scan en cours...", hw.cx("Scan en cours..."), ui.MID() - 4, 1)
    hw.oled_show()

    sta.active(True)
    try: sta.config(txpower=8)
    except: pass
    nets = []
    try:
        seen = set()
        for r in sorted(sta.scan(), key=lambda x: -x[3]):
            try:
                ssid = r[0].decode("utf-8", "ignore").strip()
            except:
                ssid = str(r[0])
            if ssid and ssid not in seen:
                seen.add(ssid)
                nets.append((ssid, r[3], r[4]))   # ssid, rssi, security
    except:
        pass

    if not nets:
        ui.message("WIFI", "Aucun reseau\ndetecte.", 2000)
        return

    def _sig(rssi):
        if rssi > -55: return "***"
        if rssi > -70: return "** "
        return "*  "

    sel = 0
    while True:
        connected = sta.isconnected()
        hw.oled.fill(0)
        ui.header("WIFI", "OK" if connected else "---")

        VIS   = 4
        start = max(0, min(sel - 1, len(nets) - VIS))
        cy    = ui.CTY()

        for i in range(VIS):
            idx = start + i
            if idx >= len(nets):
                break
            ssid_n, rssi, sec = nets[idx]
            lock = "?" if sec > 0 else " "
            sig  = _sig(rssi)
            # 9 chars SSID + 1 space + 1 lock + 3 sig = 14 chars max
            lbl  = (ssid_n[:9] + " " + lock + sig)[:14]
            y = cy + i * 10
            if idx == sel:
                hw.oled.fill_rect(0, y, C.W, 9, 1)
                hw.oled.text(lbl, 2, y + 1, 0)
            else:
                hw.oled.text(lbl, 2, y + 1, 1)

        if start > 0:
            hw.oled.text("^", C.W - 9, cy, 1)
        if start + VIS < len(nets):
            hw.oled.text("v", C.W - 9, cy + (VIS - 1) * 10, 1)

        # Label bouton A selon état
        ssid_sel, _, sec_sel = nets[sel]
        if connected:
            try:
                cur = sta.config("essid")
            except:
                cur = ""
            a_lbl = "Deconnecter" if cur == ssid_sel else "Connecter"
        else:
            a_lbl = "Connecter"

        ui.footer("Retour", a_lbl)
        hw.oled_show()

        b = hw.wait_btn(0)
        if b == "b":
            return
        elif b in ("up", "lt"):
            sel = (sel - 1) % len(nets); hw.melody(C.SND_NAV)
        elif b in ("dn", "rt"):
            sel = (sel + 1) % len(nets); hw.melody(C.SND_NAV)
        elif b == "a":
            ssid_sel, _, sec_sel = nets[sel]

            # Déconnexion si déjà connecté à ce réseau
            if connected:
                try:
                    if sta.config("essid") == ssid_sel:
                        NET.sta_disconnect()
                        hw.melody(C.SND_ERR)
                        ui.message("WIFI", "Deconnecte.", 1500)
                        continue
                except:
                    pass

            # Connexion
            saved = store.get("wifi", "sta_pwd", "")
            if sec_sel > 0 and not saved:
                ui.message("Reseau protege", "Mot de passe\nnon configure.\nConfig via /api", 3000)
                continue

            hw.oled.fill(0)
            ui.header("WIFI")
            hw.oled.text("Connexion...", hw.cx("Connexion..."), ui.MID() - 8, 1)
            hw.oled.text(ssid_sel[:15], hw.cx(ssid_sel[:15]), ui.MID() + 4, 1)
            hw.oled_show()

            ip = NET.sta_connect(ssid_sel, saved, 10000)
            if ip:
                store.put("wifi", "sta_ssid",    ssid_sel)
                store.put("wifi", "sta_enabled", True)
                store.save()
                hw.melody(C.SND_OK)
                ui.message("CONNECTE !", "IP: " + ip, 2500)
            else:
                hw.melody(C.SND_ERR)
                ui.message("ECHEC", "Connexion\nimpossible.", 2000)


def _screen_infos():
    """MAC, IP, URL dashboard."""
    mac = "??:??:??:??:??:??"
    ip  = C.AP_IP
    ap_on = False
    try:
        import network
        ap = network.WLAN(network.AP_IF)
        ap_on = ap.active()
        if ap_on:
            ip = ap.ifconfig()[0]
        try:
            mb  = ap.config("mac")
            mac = ":".join("{:02X}".format(b) for b in mb)
        except:
            pass
    except:
        pass

    mac1 = mac[:8]
    mac2 = mac[9:] if len(mac) > 9 else ""

    hw.oled.fill(0)
    ui.header("DEVICE INFO")
    cy = ui.CTY() + 1
    hw.oled.text("MAC:" + mac1,              2, cy,      1)
    hw.oled.text("    " + mac2,              2, cy +  9, 1)
    hw.oled.text("IP: " + (ip if ap_on else "AP inactif"), 2, cy + 20, 1)
    # URL en boite inversee
    url = ip + "/api"
    hw.oled.fill_rect(0, cy + 30, C.W, 9, 1)
    hw.oled.text(url[:15], max(0, (C.W - len(url[:15]) * 8) // 2), cy + 31, 0)
    ui.footer("OK")
    hw.oled_show()
    hw.wait_btn(0)


def _menu_connexion():
    """Sous-menu Connexion : Hotspot / WiFi / Infos."""
    def _ap_label():
        try:
            import network
            return "ON " if network.WLAN(network.AP_IF).active() else "OFF"
        except:
            return "---"

    def _sta_label():
        try:
            import network
            return "OK " if network.WLAN(network.STA_IF).isconnected() else "---"
        except:
            return "---"

    while True:
        items = [
            "Hotspot    [" + _ap_label() + "]",
            "WiFi       [" + _sta_label() + "]",
            "Infos device",
        ]
        sel = ui.run_menu("CONNEXION", items, lambda s: False)
        if sel is None:
            return
        if sel == 0: _screen_hotspot()
        elif sel == 1: _screen_wifi()
        elif sel == 2: _screen_infos()


# ═══════════════════════════════════════════════════════════════════════════════
# AUDIO
# ═══════════════════════════════════════════════════════════════════════════════

def _item_audio():
    son = store.get("sound", "on",     True)
    vol = store.get("sound", "volume", 2)

    while True:
        hw.oled.fill(0)
        ui.header("AUDIO")
        cy = ui.CTY() + 2

        hw.oled.text("Son:", 2, cy, 1)
        slbl = " ON " if son else " OFF"
        if son:
            hw.oled.fill_rect(40, cy, 36, 9, 1)
            hw.oled.text(slbl, 42, cy + 1, 0)
        else:
            ui.rrect(40, cy, 36, 9, 1)
            hw.oled.text(slbl, 42, cy + 1, 1)

        hw.oled.text("Vol:", 2, cy + 13, 1)
        bars = "#" * vol + "-" * (3 - vol)
        hw.oled.text("[" + bars + "]", 40, cy + 13, 1)
        hw.oled.text(("", "Faible", "Normal", "Fort")[vol], 82, cy + 13, 1)

        hw.oled.text("^v=son  <>=vol", 2, cy + 27, 1)
        ui.footer("Annuler", "OK")
        hw.oled_show()

        b = hw.wait_btn(0)
        if b in ("up", "dn"):
            son = not son
            if son: hw.tone(800, 30)
        elif b == "lt" and vol > 1:
            vol -= 1
            if son: hw.tone(440, 30)
        elif b == "rt" and vol < 3:
            vol += 1
            if son: hw.tone(660 + vol * 110, 30)
        elif b == "a":
            store.put("sound", "on", son)
            store.put("sound", "volume", vol)
            store.save()
            if son: hw.melody(C.SND_OK)
            return
        elif b == "b":
            return


# ═══════════════════════════════════════════════════════════════════════════════
# VEILLE / MODE / RESETS
# ═══════════════════════════════════════════════════════════════════════════════

def _item_veille():
    OPTIONS = [
        ("30 secondes",  30_000),
        ("1 minute",     60_000),
        ("3 minutes",   180_000),
        ("10 minutes",  600_000),
        ("Jamais",            0),
    ]
    cur = store.get("display", "sleep_ms", C.SLEEP_MS)
    sel = 0
    for i, (_, ms) in enumerate(OPTIONS):
        if ms == cur:
            sel = i; break

    def _on_sel(s):
        store.put("display", "sleep_ms", OPTIONS[s][1])
        store.save()
        hw.melody(C.SND_OK)
        return False

    ui.run_menu("VEILLE ECRAN", [o[0] for o in OPTIONS], _on_sel)


def _item_mode():
    OPTIONS = [("USB (plein CPU)", "usb"), ("ECO (batterie)", "bat")]

    def _on_sel(s):
        import machine
        m = OPTIONS[s][1]
        store.put("sys", "pwr_mode", m); store.save()
        if m == "bat":
            machine.freq(80_000_000); hw.set_contrast(10)
        else:
            machine.freq(160_000_000); hw.set_contrast(255)
        hw.melody(C.SND_OK)
        return False

    ui.run_menu("MODE ENERGIE", [o[0] for o in OPTIONS], _on_sel)


def _item_reset_ctf():
    if not ui.confirm("RESET CTF", "Effacer toute\nla progression ?"):
        return
    for _, _, _, cid in C.ATELIERS:
        if cid:
            store.put("ctf", cid, False)
    store.save()
    hw.melody(C.SND_ERR)
    ui.message("RESET OK", "Progression\neffacee !", 1500)


def _item_reset_usine():
    if not ui.confirm("RESET USINE", "Effacer TOUT ?\n(WiFi + config\n+ progression)"):
        return
    if not ui.confirm("CONFIRMER", "Vraiment tout\neffacer ?"):
        return
    store.reset()
    hw.melody(C.SND_LOSE)
    hw.oled.fill(0)
    ui.header("RESET USINE")
    hw.oled.text("Redemarrage...", hw.cx("Redemarrage..."), ui.MID() - 4, 1)
    hw.oled_show()
    time.sleep_ms(1500)
    import machine
    machine.reset()


# ═══════════════════════════════════════════════════════════════════════════════
# MENU PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════════════

def run():
    ITEMS = [
        ("Connexion",    _menu_connexion),
        ("Audio",        _item_audio),
        ("Veille",       _item_veille),
        ("Mode energie", _item_mode),
        ("Reset CTF",    _item_reset_ctf),
        ("Reset usine",  _item_reset_usine),
    ]

    def _on_sel(s):
        ITEMS[s][1]()

    ui.run_menu("REGLAGES", [i[0] for i in ITEMS], _on_sel)
