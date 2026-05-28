# net.py — Réseau Wi-Fi + Bluetooth
import network, time, config as C
from core import store

# ── Génération SSID/MDP uniques depuis l'adresse MAC ─────
def _mac_suffix():
    """6 derniers hex du MAC (3 octets) — lisible sans activer le WiFi."""
    try:
        import ubinascii, machine
        return ubinascii.hexlify(machine.unique_id()).decode().upper()[-6:]
    except:
        try:
            mac = network.WLAN(network.AP_IF).config("mac")
            return "".join("{:02X}".format(b) for b in mac[-3:])
        except:
            return "000000"

def default_ssid():
    return "ESIEAtoy_" + _mac_suffix()

def default_pwd():
    # Mot de passe = "pirate" + 4 derniers hex MAC
    return "pirate" + _mac_suffix()[-4:]

# ── Access Point ──────────────────────────────────────────
def ap_start():
    ssid = store.get("wifi","ap_ssid") or default_ssid()
    pwd  = store.get("wifi","ap_pwd")  or default_pwd()

    # Initialise les valeurs par défaut si première utilisation
    if not store.get("wifi","ap_ssid"):
        store.put("wifi","ap_ssid", ssid)
        store.put("wifi","ap_pwd",  pwd)
        store.save()

    ap = network.WLAN(network.AP_IF)
    ap.active(True)
    # Puissance réduite pour batterie (limite le pic de courant)
    try: ap.config(txpower=8)
    except: pass
    try:
        ap.config(essid=ssid, password=pwd,
                  authmode=network.AUTH_WPA_WPA2_PSK)
    except:
        try: ap.config(essid=ssid, authmode=network.AUTH_OPEN)
        except: pass
    for _ in range(30):
        if ap.active(): break
        time.sleep_ms(100)
    return ap.ifconfig()[0]

def ap_stop():
    network.WLAN(network.AP_IF).active(False)

def ap_status():
    ap = network.WLAN(network.AP_IF)
    return {
        "active": ap.active(),
        "ssid":   store.get("wifi","ap_ssid") or default_ssid(),
        "pwd":    store.get("wifi","ap_pwd")  or default_pwd(),
        "ip":     ap.ifconfig()[0] if ap.active() else None,
    }

# ── Client Wi-Fi ──────────────────────────────────────────
def sta_connect(ssid, pwd="", timeout_ms=10000):
    sta = network.WLAN(network.STA_IF)
    sta.active(True)
    try: sta.config(txpower=8)
    except: pass
    if sta.isconnected(): sta.disconnect()
    sta.connect(ssid, pwd) if pwd else sta.connect(ssid)
    t0 = time.ticks_ms()
    while not sta.isconnected():
        if time.ticks_diff(time.ticks_ms(), t0) > timeout_ms: return None
        time.sleep_ms(200)
    return sta.ifconfig()[0]

def sta_disconnect():
    sta = network.WLAN(network.STA_IF)
    sta.disconnect(); sta.active(False)
    store.put("wifi","sta_enabled",False); store.save()

def sta_scan():
    sta = network.WLAN(network.STA_IF)
    sta.active(True)
    try: sta.config(txpower=8)
    except: pass
    try:
        nets = sta.scan()
        nets.sort(key=lambda x: -x[3])
        return [{"ssid":r[0].decode("utf-8","ignore"),"rssi":r[3]} for r in nets]
    except: return []

def sta_status():
    sta = network.WLAN(network.STA_IF)
    return {
        "connected": sta.isconnected(),
        "ssid":      store.get("wifi","sta_ssid") or "",
        "ip":        sta.ifconfig()[0] if sta.isconnected() else None,
    }

# ── Bluetooth ─────────────────────────────────────────────
def bt_start():
    name = (store.get("bt","name") or default_ssid()).encode()
    try:
        import bluetooth
        ble = bluetooth.BLE()
        ble.active(True)
        adv = b"\x02\x01\x06" + bytes([len(name)+1, 0x09]) + name
        ble.gap_advertise(100, adv_data=adv)
        return True
    except: return False

def bt_stop():
    try:
        import bluetooth
        ble = bluetooth.BLE()
        try: ble.gap_advertise(None)
        except: pass
        ble.active(False)
    except: pass

def bt_status():
    try:
        import bluetooth
        return {"active": bluetooth.BLE().active()}
    except: return {"active": False}

# ── Démarrage global ──────────────────────────────────────
def start_all():
    ip = ap_start()
    if store.get("wifi","sta_enabled") and store.get("wifi","sta_ssid"):
        sta_connect(store.get("wifi","sta_ssid",""),
                    store.get("wifi","sta_pwd",""))
    if store.get("bt","enabled"):
        bt_start()
    return ip
