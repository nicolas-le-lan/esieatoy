# web.py — Serveur HTTP REST ESIEAtoy OS
import socket, json, gc, os, sys, machine, network, time
from core import store
import config as C

# ── Réponse HTTP ──────────────────────────────────────────

def _resp(conn, code, body, ctype="application/json"):
    ST = {200:"OK",201:"Created",204:"No Content",
          400:"Bad Request",401:"Unauthorized",
          403:"Forbidden",404:"Not Found",500:"Error"}
    if isinstance(body, (dict,list)): body = json.dumps(body)
    if isinstance(body, str):         body = body.encode()
    hdr = ("HTTP/1.1 " + str(code) + " " + ST.get(code,"OK") + "\r\n"
           "Content-Type: " + ctype + "; charset=utf-8\r\n"
           "Content-Length: " + str(len(body)) + "\r\n"
           "Access-Control-Allow-Origin: *\r\n"
           "Connection: close\r\n\r\n")
    conn.sendall(hdr.encode() + body)

def _send_html(conn):
    try:
        size = os.stat("/dashboard.html")[6]
        hdr  = ("HTTP/1.1 200 OK\r\n"
                "Content-Type: text/html; charset=utf-8\r\n"
                "Content-Length: " + str(size) + "\r\n"
                "Connection: close\r\n\r\n")
        conn.sendall(hdr.encode())
        with open("/dashboard.html", "rb") as f:
            while True:
                chunk = f.read(512)
                if not chunk: break
                conn.sendall(chunk)
    except:
        body = b"<h1>ESIEAtoy OS</h1><p>dashboard.html manquant. <a href=/api>API</a></p>"
        hdr  = ("HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n"
                "Content-Length: " + str(len(body)) + "\r\n"
                "Connection: close\r\n\r\n")
        conn.sendall(hdr.encode() + body)

def _send_js(conn, filename):
    try:
        size = os.stat("/" + filename)[6]
        hdr  = ("HTTP/1.1 200 OK\r\n"
                "Content-Type: application/javascript; charset=utf-8\r\n"
                "Cache-Control: max-age=31536000, public\r\n"
                "Content-Length: " + str(size) + "\r\n"
                "Connection: close\r\n\r\n")
        conn.sendall(hdr.encode())
        with open("/" + filename, "rb") as f:
            while True:
                chunk = f.read(512)
                if not chunk: break
                conn.sendall(chunk)
    except:
        _resp(conn, 404, {"error": filename + " manquant"})

# ── Parsing requête ───────────────────────────────────────

def _read(conn):
    raw = b""
    while True:
        try:
            chunk = conn.recv(512)
            if not chunk: break
            raw += chunk
            if b"\r\n\r\n" in raw:
                cl = 0
                for line in raw.split(b"\r\n"):
                    if line.lower().startswith(b"content-length:"):
                        try: cl = int(line.split(b":")[1]); break
                        except: pass
                if len(raw) - raw.index(b"\r\n\r\n") - 4 >= cl: break
        except OSError: break
    return raw.decode("utf-8","ignore")

def _parse(raw):
    try:
        lines = raw.split("\r\n")
        method, full = lines[0].split()[:2]
        path, qs = (full.split("?",1)+[""])[:2]
        hdrs = {}; body = ""; in_b = False
        for l in lines[1:]:
            if not l: in_b = True; continue
            if in_b: body += l
            elif ":" in l:
                k,v = l.split(":",1); hdrs[k.strip().lower()] = v.strip()
        return method, path, hdrs, body
    except: return "GET", "/", {}, ""

def _jb(b):
    try: return json.loads(b)
    except: return {}

# ── Auth ──────────────────────────────────────────────────

def _auth(hdrs):
    mode = store.get("auth","mode","none")
    if mode == "none": return True
    if mode == "token":
        tok = store.get("auth","token","")
        got = hdrs.get("x-api-key","") or hdrs.get("authorization","").replace("Bearer ","")
        return got == tok
    if mode == "login":
        import binascii, hashlib
        a = hdrs.get("authorization","")
        if not a.startswith("Basic "): return False
        try:
            pad = (4 - len(a.split()[1]) % 4) % 4
            u,p = binascii.a2b_base64(a.split()[1]+"="*pad).decode().split(":",1)
            h   = binascii.hexlify(hashlib.sha256(p.encode()).digest()).decode()
            return u==store.get("auth","user","admin") and h==store.get("auth","hash","")
        except: return False
    return True

# ── Filesystem ────────────────────────────────────────────

def _ls():
    out = []
    try:
        for name in sorted(os.listdir("/")):
            try:
                st = os.stat("/"+name)
                out.append({"n":name,"s":st[6],"d":bool(st[0]&0x4000),"p":name in C.SYS_FILES})
            except: out.append({"n":name,"s":0,"d":False,"p":False})
    except: pass
    try:
        for name in sorted(os.listdir("/apps")):
            if name == "__init__.py": continue
            try:
                st = os.stat("/apps/"+name)
                out.append({"n":"apps/"+name,"s":st[6],"d":False,"p":False})
            except: pass
    except: pass
    return out

def _disk():
    try:
        st=os.statvfs("/"); tot=st[0]*st[2]; free=st[0]*st[3]
        return {"total":tot//1024,"free":free//1024,"used":(tot-free)//1024,
                "pct":round((tot-free)/tot*100,1)}
    except: return {}

# ── Routeur ───────────────────────────────────────────────

def _handle(conn, raw):
    from core import notif as NOTIF
    from core import net as NET
    gc.collect()
    method, path, hdrs, body = _parse(raw)
    d = _jb(body)

    # CORS
    if method == "OPTIONS":
        conn.sendall(b"HTTP/1.1 204 No Content\r\n"
                     b"Access-Control-Allow-Origin: *\r\n"
                     b"Access-Control-Allow-Methods: GET,POST,DELETE\r\n"
                     b"Access-Control-Allow-Headers: Content-Type,X-API-Key,Authorization\r\n\r\n")
        return

    # Dashboard et Fichiers Statiques (pas d'auth)
    if method == "GET" and path == "/":
        _send_html(conn); return
    
    if method == "GET" and path == "/blockly_fr.js":
        _send_js(conn, "blockly_fr.js"); return

    # Index API (pas d'auth)
    if method == "GET" and path == "/api":
        _resp(conn, 200, {"name":"ESIEAtoy OS","version":"1.0",
            "dashboard":"http://"+C.AP_IP+"/",
            "routes":["GET /api/system","GET /api/files","GET|POST|DELETE /api/files/<n>",
                      "POST /api/exec","GET /api/exec/list","POST /api/run/<n>",
                      "GET /api/network","POST /api/network/ap","POST /api/network/sta",
                      "GET /api/network/scan","POST /api/network/bt",
                      "POST /api/reboot","GET|POST|DELETE /api/notif","GET /api/accel",
                      "GET /api/config","POST /api/config","POST /api/config/reset"]}); return

    # Auth pour le reste
    if not _auth(hdrs):
        _resp(conn, 401, {"error":"Authentification requise"}); return

    # ── Système ───────────────────────────────────────────
    if method == "GET" and path == "/api/system":
        gc.collect(); fr=gc.mem_free(); al=gc.mem_alloc()
        try: st=os.statvfs("/"); ft=st[0]*st[2]; ff=st[0]*st[3]
        except: ft=ff=0
        ap=network.WLAN(network.AP_IF); sta=network.WLAN(network.STA_IF)
        try: mac=":".join("{:02X}".format(b) for b in ap.config("mac"))
        except: mac="?"
        try:
            from esp32 import raw_temperature
            temp = str(round((raw_temperature()-32)*5/9,1))
        except: temp="N/A"
        try: nf=len(os.listdir("/"))+len(os.listdir("/apps"))
        except: nf=0
        _resp(conn,200,{"cpu_mhz":machine.freq()//1000000,
            "ram_free":fr//1024,"ram_used":al//1024,
            "flash_free":ff//1024,"flash_used":(ft-ff)//1024,
            "uptime":time.ticks_ms()//1000,"temp":temp,
            "platform":sys.platform,"mac":mac,"files":nf,
            "ap_active":ap.active(),
            "ap_ssid":store.get("wifi","ap_ssid",""),
            "ap_ip":ap.ifconfig()[0] if ap.active() else None,
            "sta_connected":sta.isconnected(),
            "sta_ip":sta.ifconfig()[0] if sta.isconnected() else None}); return

    if method == "POST" and path == "/api/reboot":
        _resp(conn,200,{"status":"rebooting"})
        conn.close(); time.sleep_ms(300); machine.reset(); return

    # ── Fichiers ──────────────────────────────────────────
    if method == "GET" and path == "/api/files":
        if "disk=1" in raw.split("\r\n")[0]: _resp(conn,200,_disk())
        else: _resp(conn,200,_ls())
        return

    if path.startswith("/api/files/"):
        name = path[11:]; fpath="/"+name
        if method == "GET":
            try:
                with open(fpath) as f: content=f.read()
                _resp(conn,200,{"name":name,"content":content,"size":len(content)})
            except: _resp(conn,404,{"error":"Introuvable"})
        elif method == "POST":
            content = d.get("content", body)
            try:
                if "/" in name:
                    try: os.mkdir("/"+name.rsplit("/",1)[0])
                    except: pass
                with open(fpath,"w") as f: f.write(content)
                _resp(conn,201,{"ok":True,"bytes":os.stat(fpath)[6]})
            except Exception as e: _resp(conn,400,{"error":str(e)})
        elif method == "DELETE":
            if name.split("/")[-1] in C.SYS_FILES:
                _resp(conn,403,{"error":"Fichier systeme protege"}); return
            try: os.remove(fpath); _resp(conn,200,{"ok":True})
            except Exception as e: _resp(conn,400,{"error":str(e)})
        return

    # ── Exec ──────────────────────────────────────────────
    if method == "POST" and path == "/api/exec":
        code=d.get("code","")
        if not code: _resp(conn,400,{"error":"code requis"}); return
        from core import runner as R; _resp(conn,200,R.exec_code(code)); return

    if method == "GET" and path == "/api/exec/list":
        from core import runner as R; _resp(conn,200,{"files":R.runnable()}); return

    if method == "POST" and path.startswith("/api/run/"):
        from core import runner as R
        _resp(conn,200,R.run_file(path[9:],d.get("bg",False))); return

    # ── Réseau ────────────────────────────────────────────
    if method == "GET" and path == "/api/network":
        ap=network.WLAN(network.AP_IF); sta=network.WLAN(network.STA_IF)
        try: import bluetooth; bt_on=bluetooth.BLE().active()
        except: bt_on=False
        _resp(conn,200,{"ap":NET.ap_status(),"sta":NET.sta_status(),
            "bt":{"active":bt_on,"name":store.get("bt","name","")}}); return

    if method == "GET" and path == "/api/network/scan":
        _resp(conn,200,{"networks":NET.sta_scan()[:12]}); return

    if method == "POST" and path == "/api/network/ap":
        ssid=d.get("ssid","").strip(); pwd=d.get("pwd","").strip()
        if ssid: store.put("wifi","ap_ssid",ssid)
        if "pwd" in d: store.put("wifi","ap_pwd",pwd)
        store.save(); NET.ap_start()
        _resp(conn,200,{"ok":True,"ssid":ssid or NET.default_ssid()}); return

    if method == "POST" and path == "/api/network/sta":
        if not d.get("connect",True):
            NET.sta_disconnect(); _resp(conn,200,{"ok":True}); return
        ssid=d.get("ssid",""); pwd=d.get("pwd","")
        store.put("wifi","sta_ssid",ssid); store.put("wifi","sta_pwd",pwd); store.save()
        ip=NET.sta_connect(ssid,pwd)
        if ip: store.put("wifi","sta_enabled",True); store.save(); _resp(conn,200,{"ok":True,"ip":ip})
        else: _resp(conn,400,{"error":"Connexion echouee"})
        return

    if method == "POST" and path == "/api/network/bt":
        name=d.get("name","").strip()
        if name: store.put("bt","name",name); store.save()
        if "enabled" in d:
            if d["enabled"]: ok=NET.bt_start(); store.put("bt","enabled",True)
            else: NET.bt_stop(); ok=True; store.put("bt","enabled",False)
            store.save(); _resp(conn,200,{"ok":ok})
        else: _resp(conn,200,{"ok":True})
        return

    # ── Notif ─────────────────────────────────────────────
    if method == "POST" and path == "/api/notif":
        msg=d.get("msg","")
        if not msg: _resp(conn,400,{"error":"msg requis"}); return
        NOTIF.push(msg,int(d.get("duration",3000))); _resp(conn,200,{"ok":True}); return
    if method == "DELETE" and path == "/api/notif":
        NOTIF.clear(); _resp(conn,200,{"ok":True}); return
    if method == "GET" and path == "/api/notif":
        _resp(conn,200,{"msg":NOTIF.get()}); return

    # ── Accéléromètre ─────────────────────────────────────
    if method == "GET" and path == "/api/accel":
        try:
            from core import accel; lis=accel.get(); x,y,z=lis.read(); tx,ty=lis.tilt()
            _resp(conn,200,{"x":round(x,1),"y":round(y,1),"z":round(z,1),
                            "tilt_x":round(tx,3),"tilt_y":round(ty,3)})
        except Exception as e: _resp(conn,503,{"error":str(e)})
        return

    # ── Config ────────────────────────────────────────────
    if method == "GET" and path == "/api/config":
        _resp(conn,200,{"sound_on":store.get("sound","on",True),
            "sound_volume":store.get("sound","volume",2),
            "auth_mode":store.get("auth","mode","none"),
            "sleep_ms":store.get("display","sleep_ms",C.SLEEP_MS)}); return

    if method == "POST" and path == "/api/config":
        if "sound_on"     in d: store.put("sound","on",   bool(d["sound_on"]))
        if "sound_volume" in d: store.put("sound","volume",int(d["sound_volume"]))
        if "auth_mode"    in d: store.put("auth","mode",  d["auth_mode"])
        if "auth_token"   in d: store.put("auth","token", d["auth_token"])
        if "auth_user"    in d: store.put("auth","user",  d["auth_user"])
        if "auth_pass"    in d:
            import binascii,hashlib
            store.put("auth","hash",
                binascii.hexlify(hashlib.sha256(d["auth_pass"].encode()).digest()).decode())
        if "sleep_ms"     in d:
            store.put("display","sleep_ms",int(d["sleep_ms"]))
            C.SLEEP_MS = int(d["sleep_ms"])
        store.save(); _resp(conn,200,{"ok":True}); return

    if method == "POST" and path == "/api/config/reset":
        store.reset(); _resp(conn,200,{"ok":True}); return

    # ── Progression CTF ───────────────────────────────────────
    if method == "GET" and path == "/api/ctf":
        import config as CFG
        ateliers = []
        done = 0
        n_ctf = 0
        for label, icon, mod, cid in CFG.ATELIERS:
            if cid is None:
                continue
            n_ctf += 1
            solved = bool(store.get("ctf", cid, False))
            if solved: done += 1
            ateliers.append({"id":cid,"label":label,"icon":icon,"solved":solved})
        _resp(conn, 200, {"ateliers":ateliers,"solved":done,"total":n_ctf}); return

    if method == "POST" and path == "/api/ctf/reset":
        import config as CFG
        for _, _, _, cid in CFG.ATELIERS:
            if cid: store.put("ctf", cid, False)
        store.save()
        _resp(conn, 200, {"ok":True}); return

    if method == "POST" and path.startswith("/api/ctf/"):
        cid = path[9:]
        val = d.get("solved", True)
        store.put("ctf", cid, bool(val))
        store.save()
        _resp(conn, 200, {"ok":True,"id":cid,"solved":bool(val)}); return

    if method == "GET" and path == "/api/ota/manifest":
        import hashlib as _hl, binascii as _bi
        manifest = {}
        def _md5(fp):
            try:
                h = _hl.md5()
                with open(fp, "rb") as f:
                    while True:
                        buf = f.read(256)
                        if not buf: break
                        h.update(buf)
                return _bi.hexlify(h.digest()).decode()
            except: return None
        for scan_dir in ("/", "/core", "/drivers", "/apps"):
            try:
                for name in os.listdir(scan_dir):
                    fpath = (scan_dir + "/" + name).replace("//", "/")
                    try:
                        if not (os.stat(fpath)[0] & 0x4000):  # not a dir
                            rel = fpath[1:]  # strip leading /
                            manifest[rel] = _md5(fpath)
                    except: pass
            except: pass
        _resp(conn, 200, manifest); return

    _resp(conn,404,{"error":"Route inconnue: "+method+" "+path})

# ── Serveur ───────────────────────────────────────────────

_sock = None

def start(port=C.WEB_PORT):
    global _sock
    if _sock: return
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", port))
    s.listen(3); s.setblocking(False)
    _sock = s

def poll():
    if not _sock: return
    try:
        conn,_ = _sock.accept(); conn.settimeout(5)
        try:
            raw=_read(conn); _handle(conn,raw)
        except Exception as e:
            try: _resp(conn,500,{"error":str(e)})
            except: pass
        finally:
            try: conn.close()
            except: pass
    except OSError: pass
    finally: gc.collect()

def stop():
    global _sock
    if _sock: _sock.close(); _sock=None
