# =============================================================================
# apps/radio_dist.py — Atelier 6 : LE RADAR (synchronisation à distance)
# =============================================================================
# STORY : Dans le coffre se trouvait un étrange appareil.
#         Deux tablettes se repoussent si trop proches, perdent le signal si
#         trop loin. Trouver et maintenir la zone de résonance 3 secondes.
#
# DÉTECTION DE DISTANCE — 3 niveaux de fallback :
#   1. ESP-NOW  : chaque tablette broadcaste un beacon toutes les 250 ms.
#                 La RSSI du signal reçu indique la distance physique.
#                 Fonctionne en mode batterie (STA seul, sans AP).
#   2. WiFi scan: scan des AP "ESIEAtoy_*" + RSSI. Mode USB uniquement.
#   3. Accéléromètre : inclinaison axe X — test solo / sans second device.
#
# ZONES RSSI (dBm) :
#   > -45  → trop proche  (rouge)
#   -45..-70 → bonne zone (vert)
#   < -70  → trop loin   (bleu)
# =============================================================================
from core import hw, ui, store
import config as C
import time

CID     = "radio_dist"
HOLD_MS = 3000

RSSI_CLOSE = -45
RSSI_FAR   = -70

_INTRO = [
    "Dans le coffre,\nun etrange\nappareil avec\nune antenne...",
    "Deux de ces\nappareils se\nrepoussent si\ntrop proches,",
    "...et perdent\nle contact si\ntrop eloignes.\nTrouvez la zone",
    "de resonance !\nBLEU  = trop loin\nVERT  = bonne zone\nROUGE = trop pres",
    "Rapprochez ou\neloignez les\ndeux tablettes.\nMaintenez 3s !",
]

# ── ESP-NOW ────────────────────────────────────────────────────────────────────
_BCAST = b'\xff\xff\xff\xff\xff\xff'
_en          = None   # instance ESPNow
_en_tx_ts    = 0      # timestamp du dernier broadcast
_en_rssi     = None   # dernière RSSI reçue d'un ESIEAtoy
_en_sta_was  = False  # état STA avant qu'on l'active


def _en_init():
    """Initialise ESP-NOW (active le STA WiFi si nécessaire). Retourne True si OK."""
    global _en, _en_sta_was
    if _en is not None:
        return True
    try:
        import espnow, network
        sta = network.WLAN(network.STA_IF)
        _en_sta_was = sta.active()
        sta.active(True)
        try: sta.config(txpower=8)
        except: pass
        e = espnow.ESPNow()
        e.active(True)
        try:
            e.add_peer(_BCAST)
        except:
            pass
        _en = e
        return True
    except Exception as ex:
        print("[radar] espnow init:", ex)
        return False


def _en_cleanup():
    """Désactive ESP-NOW et remet le STA WiFi dans son état d'origine."""
    global _en, _en_sta_was
    if _en:
        try: _en.active(False)
        except: pass
        _en = None
    if not _en_sta_was:
        try:
            import network
            network.WLAN(network.STA_IF).active(False)
        except: pass


def _en_tick():
    """
    Envoie un beacon toutes les 250 ms, draine la file de réception.
    Retourne la RSSI du dernier ESIEAtoy détecté, ou None.
    """
    global _en_tx_ts, _en_rssi
    if _en is None:
        return None

    now = time.ticks_ms()
    if time.ticks_diff(now, _en_tx_ts) >= 250:
        _en_tx_ts = now
        try:
            _en.send(_BCAST, b'ESIEAtoy')
        except:
            pass

    # Vider la file et extraire la RSSI
    try:
        while True:
            r = _en.recv(1)          # 1 ms timeout = quasi non-bloquant
            if r is None or r[0] is None:
                break
            mac, msg = r
            if not msg or b'ESIEAtoy' not in msg:
                continue
            # peers_table[mac] = [rssi, time_ms] selon les firmwares récents
            try:
                pt  = _en.peers_table
                row = pt.get(mac) if hasattr(pt, 'get') else None
                if row and len(row) >= 1:
                    rssi = int(row[0])
                    if -100 <= rssi <= 0:          # plage RSSI valide
                        _en_rssi = rssi
            except:
                _en_rssi = -60   # détecté mais RSSI non lisible → zone moyenne
    except:
        pass

    return _en_rssi


# ── WiFi RSSI scan (fallback si ESP-NOW indisponible) ─────────────────────────
_wifi_cache = [None, 0]   # [rssi, timestamp]


def _wifi_scan():
    """Scan WiFi pour un autre ESIEAtoy_* → RSSI. Résultat mis en cache 2 s."""
    now = time.ticks_ms()
    if time.ticks_diff(now, _wifi_cache[1]) < 2000:
        return _wifi_cache[0]
    _wifi_cache[1] = now
    try:
        import network
        sta = network.WLAN(network.STA_IF)
        sta.active(True)
        try: sta.config(txpower=8)
        except: pass
        best = None
        for n in sta.scan():
            try:
                ssid = n[0].decode() if isinstance(n[0], bytes) else str(n[0])
            except:
                ssid = ""
            if ssid.startswith("ESIEAtoy_"):
                rssi = n[3]
                if best is None or rssi > best:
                    best = rssi
        _wifi_cache[0] = best
    except:
        _wifi_cache[0] = None
    return _wifi_cache[0]


# ── Accéléromètre (fallback solo / sans second device) ────────────────────────
def _accel_val():
    try:
        from core import accel
        x, _, _ = accel.get().read()
        return max(0, min(350, int(abs(x))))
    except:
        import math
        return int(abs(math.sin(time.ticks_ms() / 1500.0)) * 300)


# ── Rendu ──────────────────────────────────────────────────────────────────────
def _rssi_zone(rssi):
    if rssi > RSSI_CLOSE: return "close"
    if rssi >= RSSI_FAR:  return "ok"
    return "far"


def _draw_rssi(rssi, hold_ms, mode_lbl):
    hw.oled.fill(0)
    ui.header("RADAR", "%ddB" % rssi)
    cy = ui.CTY() + 2

    pct = max(0, min(100, int((rssi + 90) * 100 / 60)))
    ui.hbar(4, cy, 120, 8, pct, 100)

    m1 = 4 + int((RSSI_FAR   + 90) * 116 / 60)
    m2 = 4 + int((RSSI_CLOSE + 90) * 116 / 60)
    hw.oled.vline(m1, cy, 8, 1)
    hw.oled.vline(m2, cy, 8, 1)

    zone = _rssi_zone(rssi)
    if zone == "ok":
        status = "BONNE ZONE!"
    elif zone == "close":
        status = "TROP PRES"
    else:
        status = "TROP LOIN"

    hw.oled.text(status, hw.cx(status), cy + 10, 1)

    if zone == "ok":
        ui.hbar(20, cy + 20, 88, 5, hold_ms, HOLD_MS)
        hw.oled.text("Maintiens !", hw.cx("Maintiens !"), cy + 27, 1)
    else:
        hw.oled.text("Cherche la zone", hw.cx("Cherche la zone"), cy + 22, 1)

    ui.footer("Annuler")
    hw.oled_show()


def _draw_accel(val, hold_ms):
    ZONE_MIN, ZONE_MAX = 80, 200
    hw.oled.fill(0)
    ui.header("RADAR", "SIM")
    cy = ui.CTY() + 2

    ui.hbar(4, cy, 120, 8, min(val, 350), 350)
    hw.oled.vline(4 + int(ZONE_MIN * 116 / 350), cy, 8, 1)
    hw.oled.vline(4 + int(ZONE_MAX * 116 / 350), cy, 8, 1)

    in_ok = ZONE_MIN <= val <= ZONE_MAX
    if in_ok:
        status = "BONNE ZONE!"
    elif val < ZONE_MIN:
        status = "TROP LOIN"
    else:
        status = "TROP PRES"

    hw.oled.text(status, hw.cx(status), cy + 10, 1)
    if in_ok:
        ui.hbar(20, cy + 20, 88, 5, hold_ms, HOLD_MS)
        hw.oled.text("Maintiens !", hw.cx("Maintiens !"), cy + 27, 1)
    else:
        hw.oled.text("Penche le badge", hw.cx("Penche le badge"), cy + 22, 1)

    ui.footer("Annuler")
    hw.oled_show()


# ── Point d'entrée ─────────────────────────────────────────────────────────────
def run():
    if store.get("ctf", CID, False):
        if not ui.confirm("DEJA RESOLU", "Rejouer cet atelier ?"):
            return

    if not ui.story_pages("RADAR", _INTRO):
        return

    # Choisir la méthode de détection : ESP-NOW en priorité, WiFi scan en fallback
    use_en   = _en_init()
    use_wifi = not use_en

    # Si aucune radio disponible : erreur, on ne tombe pas sur l'accéléromètre
    if not use_en and not use_wifi:
        ui.message("ERREUR", "WiFi indisponible.\nAtelier impossible.", 3000)
        return

    hold_start = 0
    in_zone    = False
    last_flash = 0

    try:
        while True:
            # ── Obtenir la mesure RSSI ─────────────────────────────────────────
            rssi = None
            if use_en:
                rssi = _en_tick()
            if rssi is None and use_wifi:
                rssi = _wifi_scan()

            if rssi is None:
                # Pas encore de signal détecté — afficher écran d'attente
                hw.oled.fill(0)
                ui.header("RADAR", "EN" if use_en else "WIFI")
                hw.oled.text("Recherche...", hw.cx("Recherche..."), ui.MID() - 14, 1)
                hw.oled.text("Allume l'autre", hw.cx("Allume l'autre"), ui.MID() - 4, 1)
                hw.oled.text("ESIEAtoy !", hw.cx("ESIEAtoy !"), ui.MID() + 6, 1)
                ui.footer("Annuler")
                hw.oled_show()
                b = hw.read_btn()
                if b == "b":
                    hw.led_off()
                    return
                time.sleep_ms(100)
                continue

            currently_ok = _rssi_zone(rssi) == "ok"
            now = time.ticks_ms()

            # ── Sonar dynamique "Chaud/Froid" ──────────────────────────────
            if currently_ok:
                hw.led_green()
                # Bip doux périodique toutes les 250 ms dans la bonne zone
                if time.ticks_diff(now, last_flash) >= 250:
                    last_flash = now
                    hw.tone(880, 20)
            else:
                # Calcul de proximité de 0.0 (froid) à 1.0 (chaud)
                if rssi < RSSI_FAR:
                    proximity = max(0.0, min(1.0, (rssi - (-90)) / 20.0))
                else:
                    proximity = max(0.0, min(1.0, ((-25) - rssi) / 20.0))

                # intervalle de clignotement / bip sonar
                interval = int(120 + (1.0 - proximity) * 680)

                if time.ticks_diff(now, last_flash) >= interval:
                    last_flash = now
                    zone = _rssi_zone(rssi)
                    if zone == "close":
                        hw.led_red()
                        hw.tone(1100, 16)
                    else:
                        hw.led_blue()
                        hw.tone(580, 16)
                    hw.led_off()
                else:
                    hw.led_off()

            # ── Timer de maintien ──────────────────────────────────────────────
            if currently_ok:
                if not in_zone:
                    in_zone    = True
                    hold_start = time.ticks_ms()
                hold_elapsed = time.ticks_diff(time.ticks_ms(), hold_start)
            else:
                in_zone      = False
                hold_elapsed = 0

            # ── Rendu ──────────────────────────────────────────────────────────
            lbl = "EN" if use_en else "WIFI"
            _draw_rssi(rssi, hold_elapsed, lbl)

            # ── Victoire ───────────────────────────────────────────────────────
            if currently_ok and hold_elapsed >= HOLD_MS:
                break

            b = hw.read_btn()
            if b == "b":
                hw.led_off()
                return
            time.sleep_ms(40)

    finally:
        _en_cleanup()
        hw.led_off()

    # ── Séquence de victoire ───────────────────────────────────────────────────
    hw.led_off()
    for _ in range(6):
        hw.led_green(); time.sleep_ms(80)
        hw.led_off();   time.sleep_ms(80)
    hw.melody(C.SND_WIN)

    store.put("ctf", CID, True)
    store.save()

    ui.story_pages("CONNEXION!", [
        "RESONANCE\nETABLIE !",
        "Les deux appareils\nse synchronisent.\nUn signal etrange\nest detecte...",
        "Sous le plancher\ndu navire, une\nmachine pulse\nau meme rythme !",
        "Message de fin :\nESIEA TOY\nTablette educative\nFrance 2026.",
    ])
    ui.victory("RADAR OK", "Zone trouvee !", "Atelier 6/6")
