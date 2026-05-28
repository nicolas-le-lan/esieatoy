#!/usr/bin/env python3
# =============================================================================
# flash.py -- ESIEA TOY OS -- Deploiement unifie ESP32-C3
# =============================================================================
# Usage :
#   python flash.py                   # auto-detection port, deploy complet
#   python flash.py COM4              # port explicite Windows
#   python flash.py /dev/ttyUSB0      # port explicite Linux/Mac
#   python flash.py --check           # verif. syntaxe seulement (sans upload)
#   python flash.py --clean           # efface store.json sur la carte
#   python flash.py --reset           # redemarre la carte apres upload
#   python flash.py --dry-run         # simule sans rien envoyer
#   python flash.py --diff            # upload uniquement les fichiers modifies
#   python flash.py --ota             # OTA Wi-Fi via HTTP (192.168.4.1)
#   python flash.py --ota 192.168.1.X # OTA Wi-Fi via HTTP (adresse custom)
#
# Prerequis : pip install mpremote pyserial
# =============================================================================

import argparse, ast, os, subprocess, sys, time

# -- Racine du projet (fonctionne que ce script soit a la racine ou dans tools/)
_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT  = os.path.dirname(_HERE) if os.path.basename(_HERE) == "tools" else _HERE

# -- Couleurs ANSI (Windows 10+ supporte VT100 via os.system(""))
if sys.platform == "win32":
    os.system("")
_COLOR = sys.stdout.isatty()
def _c(code, t): return "\033[" + code + "m" + t + "\033[0m" if _COLOR else t
OK   = lambda t: _c("32;1", t)
ERR  = lambda t: _c("31;1", t)
WARN = lambda t: _c("33",   t)
INFO = lambda t: _c("36",   t)
DIM  = lambda t: _c("2",    t)
BOLD = lambda t: _c("1",    t)

# -- Manifeste des fichiers ----------------------------------------------------
# Fichiers OBLIGATOIRES -- l'upload echoue si l'un d'eux est manquant localement
REQUIRED = [
    # Racine
    "config.py",
    "boot.py",
    "main.py",
    # Core OS
    "core/__init__.py",
    "core/store.py",
    "core/rand.py",
    "core/hw.py",
    "core/accel.py",
    "core/ui.py",
    "core/game_manager.py",
    "core/net.py",
    "core/runner.py",
    "core/notif.py",
    "core/web.py",
    # Drivers OLED
    "drivers/__init__.py",
    "drivers/sh1106.py",
    "drivers/ssd1306.py",
    # Apps / Puzzles
    "apps/__init__.py",
    "apps/morse.py",
    "apps/cesar.py",
    "apps/simon.py",
    "apps/crochetage.py",
    "apps/radio_dist.py",
    "apps/reglages.py",
]

# Fichiers OPTIONNELS -- uploades s'ils existent, ignores sinon
OPTIONAL = [
    "blockly_fr.js",
    "apps/accel_bruit.py",
    "apps/hack_portail.py",
    "apps/scratch_blocs.py",
]

# Repertoires a creer sur la carte (ordre : parents avant enfants)
REMOTE_DIRS = ["core", "drivers", "apps"]

# Fichiers a supprimer sur la carte avant upload (ancienne architecture)
CLEAN = [
    # Anciens fichiers racine
    "hw.py", "store.py", "ui.py", "runner.py", "notif.py",
    "accel.py", "net.py", "web.py", "store.json", "settings.json",
    # Ancien dossier puzzles/ (renomme en apps/)
    "puzzles/__init__.py", "puzzles/simon.py", "puzzles/morse.py",
    "puzzles/cesar.py", "puzzles/radio_dist.py", "puzzles/accel_bruit.py",
    "puzzles/hack_portail.py", "puzzles/scratch_blocs.py", "puzzles/reglages.py",
    # Ancien dossier apps/ (ancienne architecture)
    "apps/accel_app.py", "apps/info.py", "apps/settings.py",
    "apps/diag.py",
    # Fichiers obsoletes divers
    "server.py", "auth.py", "vfs.py", "menu.py",
]

# URL de telechargement MicroPython pour ESP32-C3
_MP_BOARD       = "ESP32_GENERIC_C3"
_MP_DL_PAGE     = "https://micropython.org/download/" + _MP_BOARD + "/"
_MP_CACHE_DIR   = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".firmware_cache")


# =============================================================================
# Helpers mpremote
# =============================================================================

def mp(*args, timeout=30):
    """Lance mpremote sans connexion (ex: version)."""
    cmd = [sys.executable, "-m", "mpremote"] + list(args)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode == 0, r.stdout + r.stderr
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return False, str(e)


def mp_port(port, *args, timeout=30):
    """Lance mpremote connect PORT <args>."""
    cmd = [sys.executable, "-m", "mpremote", "connect", port] + list(args)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode == 0, r.stdout + r.stderr
    except subprocess.TimeoutExpired:
        return False, "Timeout"
    except FileNotFoundError:
        return False, "mpremote introuvable"


# =============================================================================
# Firmware MicroPython : detection + telechargement + flash automatique
# =============================================================================

def _esptool_cmd():
    """Retourne la commande de base pour esptool, ou None si absent."""
    import shutil
    try:
        r = subprocess.run([sys.executable, "-m", "esptool", "version"],
                           capture_output=True, text=True, timeout=10)
        if r.returncode == 0:
            return [sys.executable, "-m", "esptool"]
    except Exception:
        pass
    for name in ("esptool.py", "esptool"):
        if shutil.which(name):
            return [name]
    return None


def is_micropython_present(port):
    """Retourne True si MicroPython repond sur le port."""
    ok, out = mp_port(port, "exec", "print('__mp_ok__')", timeout=8)
    return ok and "__mp_ok__" in out


def _fetch_latest_firmware_url():
    """Scrape micropython.org et retourne (url, filename) du dernier firmware stable."""
    import urllib.request, re
    try:
        with urllib.request.urlopen(_MP_DL_PAGE, timeout=15) as r:
            html = r.read().decode("utf-8", errors="replace")
    except Exception as e:
        return None, "Connexion impossible : " + str(e)

    # Liens directs /resources/firmware/ESP32_GENERIC_C3-YYYYMMDD-vX.Y.Z.bin
    pat = r'href="(/resources/firmware/' + _MP_BOARD + r'-\d{8}-v[\d.]+\.bin)"'
    matches = re.findall(pat, html)
    if not matches:
        # Liens absolus (format alternatif)
        pat2 = r'href="(https://[^"]+/' + _MP_BOARD + r'-[^"]+\.bin)"'
        matches2 = re.findall(pat2, html)
        if matches2:
            url = matches2[0]
            return url, url.split("/")[-1]
        return None, "Aucun firmware trouve sur " + _MP_DL_PAGE

    url = "https://micropython.org" + matches[0]
    return url, matches[0].split("/")[-1]


def download_micropython():
    """Telecharge le dernier firmware ESP32-C3. Retourne le chemin local ou None."""
    import urllib.request

    print(INFO("  Recherche du dernier firmware " + _MP_BOARD + "..."))
    url, info = _fetch_latest_firmware_url()
    if not url:
        print(ERR("  [ERR] " + info))
        return None

    os.makedirs(_MP_CACHE_DIR, exist_ok=True)
    dest = os.path.join(_MP_CACHE_DIR, info)

    if os.path.exists(dest):
        size_kb = os.path.getsize(dest) // 1024
        print(INFO("  Firmware en cache : " + info + "  (" + str(size_kb) + " Ko)"))
        return dest

    print(INFO("  Telechargement : " + info))

    def _progress(count, block, total):
        if total > 0:
            pct = min(100, int(count * block * 100 / total))
            bar = "#" * (pct // 3) + "." * (33 - pct // 3)
            print("  [" + bar + "] " + str(pct) + "%  ", end="\r")

    try:
        urllib.request.urlretrieve(url, dest, reporthook=_progress)
        print("  [" + "#" * 33 + "] 100%  ")
        size_kb = os.path.getsize(dest) // 1024
        print(OK("  [OK]  " + info + "  (" + str(size_kb) + " Ko)"))
        return dest
    except Exception as e:
        print(ERR("  [ERR] Telechargement echoue : " + str(e)))
        if os.path.exists(dest):
            os.remove(dest)
        return None


def flash_firmware(port, bin_path):
    """Flash le firmware MicroPython via esptool. Retourne True si succes."""
    cmd = _esptool_cmd()
    if not cmd:
        print(ERR("  [ERR] esptool introuvable"))
        print(ERR("        pip install esptool"))
        return False

    base = cmd + ["--chip", "esp32c3", "--port", port]

    print(INFO("  Effacement de la flash..."))
    r = subprocess.run(base + ["erase-flash"],
                       capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        out = (r.stdout + r.stderr).strip()
        print(ERR("  [ERR] Effacement echoue"))
        if out:
            print(ERR("        " + out[:200]))
        print(WARN("  [!]  Si le port est occupe : ferme Chrome/Edge et tout"))
        print(WARN("       outil serie ouvert (PuTTY, Arduino IDE, etc.)"))
        return False
    print(OK("  [OK]  Flash effacee"))

    print(INFO("  Ecriture du firmware (peut prendre 30-60s)..."))
    r = subprocess.run(base + ["--baud", "460800",
                                "write-flash", "-z", "0x0", bin_path],
                       capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        out = (r.stdout + r.stderr).strip()
        print(ERR("  [ERR] Ecriture echouee"))
        if out:
            print(ERR("        " + out[:200]))
        return False
    print(OK("  [OK]  Firmware installe"))

    print(INFO("  Attente du redemarrage..."))
    time.sleep(4)
    return True


def ensure_micropython(port):
    """
    Verifie que MicroPython tourne sur le port.
    Si absent : telecharge et flashe automatiquement.
    Retourne True si pret a recevoir des fichiers.
    """
    print(BOLD("\n[2b] Verification MicroPython"))

    if is_micropython_present(port):
        ok2, out2 = mp_port(port, "exec", "import sys; print(sys.version)", timeout=8)
        ver = out2.strip().split("\n")[0] if ok2 and out2.strip() else "?"
        print(OK("  [OK]  MicroPython detecte  " + DIM(ver)))
        return True

    print(WARN("  [!]  MicroPython absent ou non detecte sur " + port))
    print(INFO("  Installation automatique du firmware..."))

    bin_path = download_micropython()
    if not bin_path:
        return False

    return flash_firmware(port, bin_path)


# =============================================================================
# Etape 0 : Verification des dependances
# =============================================================================

def check_deps():
    print(BOLD("\n[0/5] Verification des dependances"))
    ok, out = mp("version")
    if not ok:
        print(ERR("  [ERR] mpremote introuvable"))
        print(ERR("        pip install mpremote"))
        return False
    ver = out.strip().split("\n")[0] if out.strip() else "?"
    print(OK("  [OK]  mpremote  " + DIM(ver)))

    try:
        import serial
        print(OK("  [OK]  pyserial"))
    except ImportError:
        print(WARN("  [!]   pyserial absent -- detection de port limitee"))
        print(WARN("        pip install pyserial"))

    if _esptool_cmd():
        print(OK("  [OK]  esptool"))
    else:
        print(WARN("  [!]   esptool absent -- flash firmware impossible"))
        print(WARN("        pip install esptool"))

    return True


# =============================================================================
# Etape 1 : Verification syntaxe Python
# =============================================================================

def check_syntax(files):
    print(BOLD("\n[1/5] Verification syntaxe Python"))
    errors = []
    for rel in files:
        if not rel.endswith(".py"):
            continue
        path = os.path.join(ROOT, rel)
        if not os.path.exists(path):
            continue
        try:
            with open(path, encoding="utf-8") as f:
                ast.parse(f.read(), filename=rel)
        except SyntaxError as e:
            errors.append((rel, e))
            print(ERR("  [ERR] " + rel))
            print(ERR("        " + str(e)))

    n = sum(1 for r in files if r.endswith(".py")
            and os.path.exists(os.path.join(ROOT, r)))
    if errors:
        print(ERR("\n  " + str(len(errors)) + " erreur(s) -- deploiement annule"))
        return False
    print(OK("  [OK]  " + str(n) + " fichier(s) Python valides"))
    return True


# =============================================================================
# Etape 2 : Detection du port serie
# =============================================================================

def detect_port():
    try:
        import serial.tools.list_ports
        KEYWORDS = ["esp", "ch340", "cp210", "cp2102", "ftdi", "uart",
                    "usb serial", "silicon labs", "wch", "jtag"]
        all_ports = list(serial.tools.list_ports.comports())
        # 1. Recherche par mots-cles (identification certaine)
        candidates = []
        for p in all_ports:
            txt = ((p.description or "") + (p.hwid or "")).lower()
            if any(k in txt for k in KEYWORDS):
                candidates.append(p.device)
        if len(candidates) == 1:
            return candidates[0]
        if len(candidates) > 1:
            print(INFO("  Plusieurs ports ESP32 detectes : " + ", ".join(candidates)))
            print(INFO("  Utilisation de : " + candidates[0]))
            return candidates[0]
        # 2. Fallback : un seul port disponible -> on l'utilise directement
        if len(all_ports) == 1:
            port = all_ports[0].device
            desc = all_ports[0].description or "?"
            print(INFO("  Port unique detecte : " + port + " (" + desc + ")"))
            return port
        # 3. Plusieurs ports sans identification -> lister et demander
        if all_ports:
            names = [p.device for p in all_ports]
            print(WARN("  Ports disponibles : " + ", ".join(names)))
            print(WARN("  Precisez le port : python flash.py " + names[0]))
        return None
    except ImportError:
        pass

    # Sans pyserial : scan COM (Windows) ou glob (Linux/Mac)
    if sys.platform == "win32":
        for i in range(20, 0, -1):
            ok, _ = mp_port("COM" + str(i), "ls", ":", timeout=4)
            if ok:
                return "COM" + str(i)
    else:
        import glob
        for p in glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*"):
            return p
    return None


# =============================================================================
# Rétroaction physique sur le badge (LED / Son / OLED)
# =============================================================================

def show_flashing_status_on_device(port):
    script = (
        "try:\n"
        "    from core import hw, ui\n"
        "    hw.oled.fill(0)\n"
        "    ui.header('MAJ SYSTEME')\n"
        "    hw.oled.text('CONNEXION PC...', 8, 22, 1)\n"
        "    hw.oled.text('TELEVERSEMENT...', 4, 34, 1)\n"
        "    ui.footer('Patienter')\n"
        "    hw.oled_show()\n"
        "except: pass\n"
    )
    mp_port(port, "exec", script, timeout=10)


def show_flash_progress_on_device(port, current, total):
    pct = int(current * 100 / total) if total > 0 else 0
    bars = pct // 10
    bar_str = "[" + "#" * bars + "." * (10 - bars) + "]"
    script = (
        "try:\n"
        "    from core import hw, ui\n"
        "    hw.oled.fill(0)\n"
        "    ui.header('TELEVERSEMENT')\n"
        f"    hw.oled.text('PROGRES: {pct}%', 16, 22, 1)\n"
        f"    hw.oled.text('{current}/{total} FICHIERS', 12, 34, 1)\n"
        f"    ui.footer('{bar_str}')\n"
        "    hw.oled_show()\n"
        "except: pass\n"
    )
    mp_port(port, "exec", script, timeout=10)


def show_flash_complete_on_device(port):
    script = (
        "try:\n"
        "    from core import hw, ui\n"
        "    hw.oled.fill(0)\n"
        "    ui.header('MAJ COMPLETE')\n"
        "    hw.led_green()\n"
        "    hw.oled.text('SUCCES !', 36, 20, 1)\n"
        "    hw.oled.text('MAJ TERMINEE !', 12, 32, 1)\n"
        "    ui.footer('Reboot / RST')\n"
        "    hw.oled_show()\n"
        "    import config as C\n"
        "    hw.melody(C.SND_WIN)\n"
        "    hw.led_off()\n"
        "except: pass\n"
    )
    mp_port(port, "exec", script, timeout=10)


# =============================================================================
# Etape 3 : Nettoyage + creation de dossiers
# =============================================================================

def prepare_card(port, dry_run=False):
    print(BOLD("\n[2/5] Preparation de la carte"))

    if dry_run:
        print(DIM("  [dry-run] Nettoyage + mkdir ignores"))
        return

    removed = 0
    for f in CLEAN:
        ok, _ = mp_port(port, "rm", ":" + f, timeout=8)
        if ok:
            removed += 1

    if removed:
        print(OK("  [OK]  " + str(removed) + " ancien(s) fichier(s) supprime(s)"))

    for d in REMOTE_DIRS:
        mp_port(port, "mkdir", ":" + d, timeout=8)
    print(OK("  [OK]  Dossiers : " + ", ".join(REMOTE_DIRS)))

    show_flashing_status_on_device(port)


# =============================================================================
# Helpers upload
# =============================================================================

def _build_upload_list():
    """Returns [(rel, local_path, required), ...] or None on error."""
    result = []
    for rel in REQUIRED:
        path = os.path.join(ROOT, rel)
        if not os.path.exists(path):
            print(ERR("  [ERR] MANQUANT : " + rel))
            return None
        result.append((rel, path, True))
    for rel in OPTIONAL:
        path = os.path.join(ROOT, rel)
        if os.path.exists(path):
            result.append((rel, path, False))
        else:
            print(DIM("  [~]   " + rel + "  (optionnel, absent)"))
    return result


def _do_upload_usb(port, to_upload, dry_run=False):
    """Upload a specific list of files via mpremote cp."""
    total_bytes = sum(os.path.getsize(p) for _, p, _ in to_upload)
    n = len(to_upload)
    failed = []

    if not dry_run:
        show_flash_progress_on_device(port, 0, n)

    checkpoints = [1, int(n * 0.25), int(n * 0.50), int(n * 0.75), n]
    checkpoints = sorted(list(set(c for c in checkpoints if c >= 1)))

    for i, (rel, path, required) in enumerate(to_upload, 1):
        size = os.path.getsize(path)
        pct  = int((i - 1) / n * 30)
        print("  [" + "#" * pct + "." * (30 - pct) + "] "
              + str(i) + "/" + str(n) + " " + rel, end="\r")

        if dry_run:
            time.sleep(0.02)
            print(DIM("  [->]  " + ("%-42s" % rel) + "  " + str(size) + " o  [dry]"))
            continue

        ok, out = mp_port(port, "cp", path, ":" + rel, timeout=20)
        if ok:
            print(OK("  [->]  ") + ("%-42s" % rel) + DIM("  " + str(size) + " o"))
            if not dry_run and i in checkpoints:
                show_flash_progress_on_device(port, i, n)
        else:
            print(ERR("  [ERR] " + rel))
            if out.strip():
                print(ERR("        " + out.strip()[:100]))
            if required:
                failed.append(rel)

    print("  [" + "#" * 30 + "] " + str(n) + "/" + str(n) + " termine")

    if failed:
        print(ERR("\n  " + str(len(failed)) + " fichier(s) en echec"))
        return False
    print(OK("\n  [OK]  " + str(n) + " fichiers  |  " + str(total_bytes) + " octets"))
    return True


# =============================================================================
# Etape 4 : Upload
# =============================================================================

def upload(port, dry_run=False):
    print(BOLD("\n[3/5] Upload des fichiers"))
    to_upload = _build_upload_list()
    if to_upload is None:
        return False
    return _do_upload_usb(port, to_upload, dry_run)


# =============================================================================
# Helpers MD5 et manifest
# =============================================================================

def local_md5(path):
    import hashlib
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            h.update(chunk)
    return h.hexdigest()


def get_manifest_usb(port, files):
    """Returns dict {rel_path: md5_hex or None} via mpremote exec."""
    script = (
        "import hashlib,binascii,json\n"
        "m={}\n"
        "for f in " + repr(files) + ":\n"
        "    try:\n"
        "        h=hashlib.md5()\n"
        "        fp=open('/'+f,'rb')\n"
        "        while True:\n"
        "            b=fp.read(256)\n"
        "            if not b:break\n"
        "            h.update(b)\n"
        "        fp.close()\n"
        "        m[f]=binascii.hexlify(h.digest()).decode()\n"
        "    except:m[f]=None\n"
        "print(json.dumps(m))\n"
    )
    ok, out = mp_port(port, "exec", script, timeout=45)
    if not ok:
        return None
    import json
    for line in reversed(out.strip().split("\n")):
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except:
                pass
    return None


def get_manifest_http(host):
    """Returns dict {rel_path: md5_hex or None} via HTTP GET /api/ota/manifest."""
    import urllib.request, json
    try:
        url = "http://" + host + "/api/ota/manifest"
        with urllib.request.urlopen(url, timeout=10) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print(WARN("  [!] Manifest HTTP impossible : " + str(e)))
        return None


def ota_upload_file(host, rel, local_path):
    """Upload one file via POST /api/files/<rel>. Returns True on success."""
    import urllib.request, json
    try:
        with open(local_path, "rb") as f:
            content = f.read().decode("utf-8", errors="replace")
        data = json.dumps({"content": content}).encode("utf-8")
        url = "http://" + host + "/api/files/" + rel
        req = urllib.request.Request(
            url, data=data,
            headers={"Content-Type": "application/json",
                     "Content-Length": str(len(data))}
        )
        req.get_method = lambda: "POST"
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status in (200, 201)
    except Exception as e:
        print(ERR("        " + str(e)[:80]))
        return False


def ota_reboot(host):
    import urllib.request
    try:
        data = b"{}"
        req = urllib.request.Request(
            "http://" + host + "/api/reboot", data=data,
            headers={"Content-Type": "application/json"}
        )
        req.get_method = lambda: "POST"
        urllib.request.urlopen(req, timeout=5)
    except:
        pass  # device reboots = connection closed = exception expected


# =============================================================================
# Upload incremental USB (diff)
# =============================================================================

def upload_diff_usb(port, dry_run=False):
    print(BOLD("\n[3/5] Upload incremental (diff USB)"))
    to_upload = _build_upload_list()
    if to_upload is None:
        return False

    all_rels = [rel for rel, _, _ in to_upload]
    print(INFO("  Calcul des MD5 sur la carte..."))
    device_manifest = get_manifest_usb(port, all_rels)
    if device_manifest is None:
        print(WARN("  [!] Manifest indisponible -- upload complet"))
        return upload(port, dry_run)

    changed = []
    unchanged = 0
    for rel, path, required in to_upload:
        lhash = local_md5(path)
        dhash = device_manifest.get(rel)
        if lhash != dhash:
            changed.append((rel, path, required))
        else:
            unchanged += 1

    print(DIM("  [~]  " + str(unchanged) + " fichier(s) inchange(s) ignores"))
    if not changed:
        print(OK("  [OK] Rien a mettre a jour !"))
        return True

    print(INFO("  " + str(len(changed)) + " fichier(s) a mettre a jour"))
    return _do_upload_usb(port, changed, dry_run)


# =============================================================================
# Upload OTA Wi-Fi
# =============================================================================

def upload_ota(host, diff=False, dry_run=False):
    print(BOLD("\n[3/5] OTA Wi-Fi -> http://" + host))
    to_upload = _build_upload_list()
    if to_upload is None:
        return False

    device_manifest = {}
    if diff:
        print(INFO("  Recuperation du manifest..."))
        device_manifest = get_manifest_http(host) or {}

    changed = []
    unchanged = 0
    for rel, path, required in to_upload:
        if diff:
            lhash = local_md5(path)
            dhash = device_manifest.get(rel)
            if lhash == dhash:
                unchanged += 1
                continue
        changed.append((rel, path, required))

    if diff:
        print(DIM("  [~]  " + str(unchanged) + " fichier(s) inchange(s) ignores"))
    if not changed:
        print(OK("  [OK] Rien a mettre a jour !"))
        return True

    total_bytes = sum(os.path.getsize(p) for _, p, _ in changed)
    n = len(changed)
    failed = []

    for i, (rel, path, required) in enumerate(changed, 1):
        size = os.path.getsize(path)
        print("  [" + "#" * int((i-1)/n*30) + "." * (30-int((i-1)/n*30)) + "] "
              + str(i) + "/" + str(n) + " " + rel, end="\r")

        if dry_run:
            print(DIM("  [->]  " + ("%-42s" % rel) + "  " + str(size) + " o  [dry]"))
            continue

        ok = ota_upload_file(host, rel, path)
        if ok:
            print(OK("  [->]  ") + ("%-42s" % rel) + DIM("  " + str(size) + " o"))
        else:
            print(ERR("  [ERR] " + rel))
            if required:
                failed.append(rel)

    print("  [" + "#" * 30 + "] " + str(n) + "/" + str(n) + " termine")

    if failed:
        print(ERR("\n  " + str(len(failed)) + " fichier(s) en echec"))
        return False
    print(OK("\n  [OK]  " + str(len(changed)) + " fichiers  |  " + str(total_bytes) + " octets"))
    return True


# =============================================================================
# Etape 5 : Verification sur la carte
# =============================================================================

def verify(port):
    print(BOLD("\n[4/5] Verification sur la carte"))
    key = ["config.py", "main.py", "boot.py",
           "core/hw.py", "core/ui.py", "core/game_manager.py",
           "drivers/sh1106.py", "apps/morse.py", "apps/simon.py"]
    script = (
        "import os\n"
        "ok,miss=[],[]\n"
        "for f in " + repr(key) + ":\n"
        "    try:\n"
        "        os.stat(f); ok.append(f)\n"
        "    except:\n"
        "        miss.append(f)\n"
        "print('OK:',len(ok),'MISSING:',miss)\n"
    )
    ok, out = mp_port(port, "exec", script, timeout=15)
    if ok and out.strip():
        lines = [l for l in out.strip().split("\n") if "OK:" in l]
        if lines:
            print(OK("  [OK]  " + lines[-1].strip()))
            return "MISSING: []" in lines[-1]
    print(WARN("  [!]  Verification impossible (normal si reset deja envoye)"))
    return True


# =============================================================================
# Helpers optionnels : reset + clean store
# =============================================================================

def do_reset(port):
    print(BOLD("\n[5/5] Redemarrage"))
    ok, _ = mp_port(port, "reset", timeout=10)
    if ok:
        print(OK("  [OK]  Reset envoye"))
    else:
        print(WARN("  [!]   Reset non confirme -- appuyez sur RST ou rebranchez le cable"))


def do_clean_store(port, dry_run=False):
    print(INFO("\n  [--clean] Suppression de /store.json..."))
    if dry_run:
        print(DIM("  [dry-run] ignore"))
        return
    ok, _ = mp_port(port, "exec", "import os; os.remove('/store.json')", timeout=8)
    if ok:
        print(OK("  [OK]  /store.json supprime (progression & config reinitialisees)"))
    else:
        print(DIM("  [~]   /store.json absent"))


# =============================================================================
# Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        prog="flash.py",
        description="Deploie ESIEA TOY OS sur ESP32-C3",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
exemples :
  python flash.py                      # auto-detect, deploy complet
  python flash.py COM4                 # port Windows explicite
  python flash.py /dev/ttyUSB0         # port Linux/Mac
  python flash.py --check              # verif. syntaxe uniquement
  python flash.py --clean --reset      # reset config + reboot apres upload
  python flash.py --dry-run            # simulation sans ecriture
  python flash.py --diff               # upload uniquement les fichiers modifies
  python flash.py --ota                # OTA Wi-Fi (192.168.4.1)
  python flash.py --ota 192.168.1.42   # OTA Wi-Fi (adresse custom)
  python flash.py --ota --diff         # OTA incremental (diff MD5)
        """,
    )
    parser.add_argument("port",      nargs="?", default=None,
                        help="Port serie (ex: COM4, /dev/ttyUSB0)")
    parser.add_argument("--check",   action="store_true",
                        help="Verification syntaxe seulement")
    parser.add_argument("--clean",   action="store_true",
                        help="Efface store.json (reset progression)")
    parser.add_argument("--reset",   action="store_true",
                        help="Redemarre la carte apres upload")
    parser.add_argument("--dry-run", action="store_true",
                        help="Simule sans rien envoyer")
    parser.add_argument("--diff",    action="store_true",
                        help="Upload uniquement les fichiers modifies (comparaison MD5)")
    parser.add_argument("--ota",     nargs="?", const="192.168.4.1", default=None,
                        metavar="HOST",
                        help="OTA Wi-Fi via HTTP (defaut: 192.168.4.1)")
    args = parser.parse_args()

    all_files = REQUIRED + [f for f in OPTIONAL
                            if os.path.exists(os.path.join(ROOT, f))]

    # -- Banniere ---------------------------------------------------------------
    proj = ROOT[:34] if len(ROOT) <= 34 else "..." + ROOT[-31:]
    print(BOLD("+------------------------------------------+"))
    print(BOLD("|   ESIEA TOY OS -- Flash                  |"))
    print(BOLD("|------------------------------------------|"))
    print(BOLD("|  Projet : " + "%-32s" % proj + "|"))
    print(BOLD("+------------------------------------------+"))

    # -- Etape 0 : dependances --------------------------------------------------
    if not check_deps():
        sys.exit(1)

    # -- Etape 1 : syntaxe ------------------------------------------------------
    if not check_syntax(all_files):
        sys.exit(1)

    if args.check:
        print(OK("\n  --check : OK, pas de deploiement."))
        sys.exit(0)

    if args.dry_run:
        print(WARN("\n  Mode dry-run : aucun fichier ne sera envoye.\n"))

    # -- Mode OTA Wi-Fi ---------------------------------------------------------
    if args.ota:
        host = args.ota
        print(BOLD("\n[2/5] Mode OTA Wi-Fi -> " + host))
        print(INFO("  (pas de cable USB -- upload HTTP direct)"))

        if args.clean:
            print(WARN("  [!] --clean ignore en mode OTA (necessite USB)"))

        t0 = time.time()
        if not upload_ota(host, diff=args.diff, dry_run=args.dry_run):
            sys.exit(1)
        elapsed = time.time() - t0

        print(BOLD("\n[4/5] Verification -- ignoree en mode OTA"))

        if args.reset and not args.dry_run:
            print(BOLD("\n[5/5] Redemarrage OTA"))
            ota_reboot(host)
            print(OK("  [OK]  Reset envoye"))

        n_opt = sum(1 for f in OPTIONAL if os.path.exists(os.path.join(ROOT, f)))
        dur = "%.1fs" % elapsed
        print(BOLD("\n+------------------------------------------+"))
        print(BOLD("|  [OK] Flash OTA termine !                |"))
        print(BOLD("|------------------------------------------|"))
        print(BOLD("|  Fichiers : " + str(len(REQUIRED)) + " requis + " + str(n_opt) + " optionnels" + " " * 14 + "|"))
        print(BOLD("|  Duree    : " + "%-29s" % dur + "|"))
        print(BOLD("|------------------------------------------|"))
        print(BOLD("|  -> Web   : http://" + "%-22s" % host + "|"))
        print(BOLD("+------------------------------------------+\n"))
        sys.exit(0)

    # -- Etape 2 : port serie ---------------------------------------------------
    print(BOLD("\n[2/5] Port serie"))
    port = args.port or detect_port()
    if not port:
        print(ERR("  [ERR] Aucun port trouve."))
        print(ERR("        Precisez le port : python flash.py COM4"))
        sys.exit(1)
    print(OK("  [OK]  " + BOLD(port)))

    # -- Etape 2b : verification / installation MicroPython --------------------
    if not args.dry_run:
        if not ensure_micropython(port):
            sys.exit(1)

    # -- Clean store optionnel --------------------------------------------------
    if args.clean:
        do_clean_store(port, args.dry_run)

    # -- Etape 3 : preparation --------------------------------------------------
    prepare_card(port, args.dry_run)

    # -- Etape 4 : upload -------------------------------------------------------
    t0 = time.time()
    if args.diff:
        if not upload_diff_usb(port, args.dry_run):
            sys.exit(1)
    else:
        if not upload(port, args.dry_run):
            sys.exit(1)
    elapsed = time.time() - t0

    # -- Etape 5 : verification -------------------------------------------------
    if not args.dry_run:
        verify(port)
        show_flash_complete_on_device(port)

    # -- Reset optionnel --------------------------------------------------------
    if args.reset and not args.dry_run:
        do_reset(port)

    # -- Resume final -----------------------------------------------------------
    n_opt = sum(1 for f in OPTIONAL if os.path.exists(os.path.join(ROOT, f)))
    dur = "%.1fs" % elapsed
    print(BOLD("\n+------------------------------------------+"))
    print(BOLD("|  [OK] Flash termine !                    |"))
    print(BOLD("|------------------------------------------|"))
    print(BOLD("|  Fichiers : " + str(len(REQUIRED)) + " requis + " + str(n_opt) + " optionnels" + " " * 14 + "|"))
    print(BOLD("|  Duree    : " + "%-29s" % dur + "|"))
    print(BOLD("|------------------------------------------|"))
    if not args.reset:
        print(BOLD("|  -> Rebranche le cable USB ou appuie RST |"))
    print(BOLD("|  -> Wi-Fi : ESIEAtoy_XXXX                |"))
    print(BOLD("|  -> Web   : http://192.168.4.1            |"))
    print(BOLD("+------------------------------------------+\n"))


if __name__ == "__main__":
    main()
