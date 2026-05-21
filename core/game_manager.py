# =============================================================================
# core/game_manager.py — Machine à états ESIEA TOY OS
# =============================================================================
# États :
#   BOOT    → animation démarrage + choix mode ECO/USB
#   STORY   → narration intro Barbe Noire (premier boot uniquement)
#   HOME    → menu carousel des ateliers
#   PUZZLE  → atelier en cours d'exécution
#   VICTORY → épilogue (tous les ateliers CTF résolus)
# =============================================================================
import gc, sys, time
import config as C
from core import hw, ui, store

STATE_BOOT    = "boot"
STATE_STORY   = "story"
STATE_HOME    = "home"
STATE_PUZZLE  = "puzzle"
STATE_VICTORY = "victory"
STATE_SLEEP   = "sleep"

# Konami code : UP UP DN DN LT RT LT RT A B
_KONAMI = ("up","up","dn","dn","lt","rt","lt","rt","b","a")


class GameManager:

    _STORY_PAGES = [
        "Caraibes, 1700.\nVous etes l equipage\ndu Queen Anne's\nRevenge.",
        "Apres une\nexpedition aux\niles Caimans\nvous trouvez...",
        "...un tresor !\nPieces, bijoux\net de mysterieuses\ntablettes.",
        "Sur chacune\nun etrange mot :\n\n  esieatoy",
        "Barbe Noire\nvous ordonne\nde les etudier.\nElles cachent...",
        "...un secret !\nOu une puissance\ncapable de dominer\nles mers.",
        "Soudain !\nLumieres, symboles,\nl objet se met\na vibrer !",
        "L equipage crie\na la malediction.\nBarbe Noire,\nfurieux :",
        "TROIS JOURS\npour decouvrir\nd ou ca vient\net a quoi ca sert.",
        "Sinon, ce sera\nLE CACHOT\nA VIE !\nAu travail !",
    ]

    _VICTORY_PAGES = [
        "Les tablettes\nsont des objets\ndu futur.",
        "Venues de France\nen 2026 !\nElles guident ceux\nqui voyagent",
        "...entre les\nepoques.",
        "Barbe Noire entre\net demande des\nexplications !",
        "CHOIX 1 :\nLui dire la verite.\nIl sourit et dit\nCap sur l avenir !",
        "A moi les tresors\ndu temps !",
        "CHOIX 2 :\nCacher la machine\net dire que vous\nn avez rien trouve.",
        "Vous fuyez alors\navec la machine\npour profiter des\ntresors du temps !",
    ]

    def __init__(self):
        self.state        = STATE_BOOT
        self.prev_state   = None
        self.atelier_idx  = 0
        self._redraw      = True
        self._last_gc     = time.ticks_ms()
        self._ox          = 0
        self._oy          = 0
        self._accel_ts    = 0
        self._konami_pos  = 0   # position courante dans _KONAMI
        hw.set_tick_hook(self._sys_tick)

    def _sys_tick(self):
        """Tick système appelé en tâche de fond (multitâche)"""
        try:
            from core import web, notif
            web.poll()
            notif.tick()
        except:
            pass

    # ── Boucle principale ──────────────────────────────────────────────────────

    def run(self):
        self._go(STATE_BOOT)
        while True:
            try:
                self._tick()
            except Exception as err:
                print("[GM] exception:", err)
                ui.crash_screen(str(err))
                self._go(STATE_HOME)

    # ── Transitions ───────────────────────────────────────────────────────────

    def _go(self, new_state, **kwargs):
        self.prev_state = self.state
        self.state      = new_state
        self._redraw    = True
        print("[GM]", self.prev_state, "->", new_state)
        if   new_state == STATE_BOOT:    self._enter_boot()
        elif new_state == STATE_STORY:   self._enter_story()
        elif new_state == STATE_HOME:    self._enter_home()
        elif new_state == STATE_PUZZLE:  self._enter_puzzle(kwargs.get("idx", self.atelier_idx))
        elif new_state == STATE_VICTORY: self._enter_victory()

    def _tick(self):
        now = time.ticks_ms()
        if time.ticks_diff(now, self._last_gc) > 8000:
            gc.collect()
            self._last_gc = now

        # Veille écran
        if self.state != STATE_SLEEP and hw.sleep_tick():
            self.prev_state = self.state
            self.state      = STATE_SLEEP
            return

        if self.state == STATE_SLEEP:
            if hw.any_btn_pressed():
                hw.wake(); hw.touch()
                self.state   = self.prev_state or STATE_HOME
                self._redraw = True
            else:
                time.sleep_ms(20)
            return

        if self.state == STATE_HOME:
            self._tick_home()

    # ── BOOT ──────────────────────────────────────────────────────────────────

    def _enter_boot(self):
        import machine
        # ── Fréquence sécurisée immédiatement ────────────────────────────────
        # Déjà réduite dans main.py, mais on le reconfirme ici par sécurité.
        machine.freq(80_000_000)

        mode   = store.get("sys", "pwr_mode", "bat")  # bat = défaut sécurisé
        choice = None

        # Pas de LED pendant l'animation — led_white() (3 LEDs = ~60 mA)
        # provoque une chute de tension sur batterie qui corrompt l'I2C OLED.
        for step in range(1, 23):
            b = hw.read_btn()
            if b == "b":   choice = "bat"
            elif b == "a": choice = "usb"

            hw.oled.fill(0)

            # Logo tablette — apparaît dès le début
            ui.draw_icon("esiea", 56, 4)

            # Séparateur + titre (step 5+)
            if step >= 5:
                hw.oled.hline(12, 23, hw.W - 24, 1)
                hw.oled.text("ESIEA TOY OS", hw.cx("ESIEA TOY OS"), 26, 1)

            # Sous-titre + 2e séparateur (step 10+)
            if step >= 10:
                hw.oled.text("Caraibes,  1700", hw.cx("Caraibes,  1700"), 36, 1)
                hw.oled.hline(12, 46, hw.W - 24, 1)

            # Pastilles de mode ECO / USB (step 14+)
            if step >= 14:
                is_bat = (choice if choice else mode) == "bat"
                if is_bat:
                    hw.oled.fill_rect(14, 49, 40, 10, 1)
                    hw.oled.text("ECO", 23, 50, 0)
                    hw.oled.rect(74, 49, 40, 10, 1)
                    hw.oled.text("USB", 83, 50, 1)
                else:
                    hw.oled.rect(14, 49, 40, 10, 1)
                    hw.oled.text("ECO", 23, 50, 1)
                    hw.oled.fill_rect(74, 49, 40, 10, 1)
                    hw.oled.text("USB", 83, 50, 0)

            # Barre de progression fine 2 px au bas de l'écran
            hw.oled.fill_rect(0, 62, step * hw.W // 22, 2, 1)

            hw.oled_show()
            time.sleep_ms(45)

        if choice is not None:
            mode = choice
            store.put("sys", "pwr_mode", mode)
            store.save()

        if mode == "bat":
            # Déjà à 80 MHz — s'assurer que le WiFi est bien éteint
            hw.set_contrast(10)
            try:
                import network
                network.WLAN(network.STA_IF).active(False)
                network.WLAN(network.AP_IF).active(False)
            except:
                pass
        else:
            # Mode USB : monter en fréquence puis démarrer le réseau
            machine.freq(160_000_000)
            hw.set_contrast(255)
            try:
                from core import net, web
                net.ap_start()
                web.start()
            except Exception as e:
                print("[boot] net start err:", e)

        lbl = "MODE ECO" if mode == "bat" else "MODE USB"
        hw.oled.fill(0)
        ui.draw_icon("esiea", 56, 4)
        lw = len(lbl) * 8 + 8
        lx = (hw.W - lw) // 2
        hw.oled.fill_rect(lx, 30, lw, 11, 1)
        hw.oled.text(lbl, lx + 4, 31, 0)
        hw.oled_show()
        hw.led_blue() if mode == "bat" else hw.led_green()
        hw.melody(C.SND_BOOT)
        time.sleep_ms(400)
        hw.led_off()

        if store.get("os", "first_boot", True):
            self._go(STATE_STORY)
        else:
            self._go(STATE_HOME)

    # ── STORY ─────────────────────────────────────────────────────────────────

    def _enter_story(self):
        hw.oled.fill(0)
        ui.draw_icon("anchor", 56, 10)
        hw.oled.text("ESIEA TOY", hw.cx("ESIEA TOY"), 32, 1)
        hw.oled.text("Caraibes, 1700", hw.cx("Caraibes, 1700"), 42, 1)
        hw.oled_show()
        hw.melody(C.SND_UNLOCK)
        time.sleep_ms(1200)

        ui.story_pages("BARBE NOIRE", self._STORY_PAGES)
        store.put("os", "first_boot", False)
        store.save()
        self._go(STATE_HOME)

    # ── HOME ──────────────────────────────────────────────────────────────────

    def _enter_home(self):
        self._redraw = True

    def _tick_home(self):
        now = time.ticks_ms()

        # Parallaxe accéléromètre (throttle 120 ms)
        if time.ticks_diff(now, self._accel_ts) > 120:
            try:
                from core import accel
                tx, ty   = accel.get().tilt()
                self._ox = int(tx * 3)
                self._oy = int(ty * 3)
            except:
                self._ox = self._oy = 0
            self._accel_ts = now

        if self._redraw and hw.is_awake():
            self._draw_home()
            self._redraw = False

        b = hw.read_btn()
        if not b:
            lbl = C.ATELIERS[self.atelier_idx][0]
            if len(lbl) > 12:
                self._redraw = True
            time.sleep_ms(10)
            return

        hw.touch()
        self._redraw = True

        # ── Konami code ──────────────────────────────────────────────────
        in_seq = self._konami_pos > 0
        if b == _KONAMI[self._konami_pos]:
            self._konami_pos += 1
            if self._konami_pos == len(_KONAMI):
                self._konami_pos = 0
                self._activate_dev_mode()
            return   # appui correct absorbé — aucun effet de bord
        else:
            self._konami_pos = 1 if b == _KONAMI[0] else 0
            if in_seq and b in ("a", "b"):
                return   # A/B incorrects mid-séquence : absorbés sans action

        if b in ("lt", "up"):
            self.atelier_idx = (self.atelier_idx - 1) % len(C.ATELIERS)
            hw.melody(C.SND_NAV)
        elif b in ("rt", "dn"):
            self.atelier_idx = (self.atelier_idx + 1) % len(C.ATELIERS)
            hw.melody(C.SND_NAV)
        elif b == "a":
            if self._is_unlocked(self.atelier_idx):
                hw.melody(C.SND_CONFIRM)
                self._go(STATE_PUZZLE, idx=self.atelier_idx)
            else:
                hw.melody(C.SND_ERR)
                ui.message("VERROUILLE", "Resous d'abord\nl'atelier precedent !", 2500)
                self._redraw = True
        elif b == "b":
            self._show_progress()

    def _is_unlocked(self, idx):
        """Retourne True si l'atelier est accessible (séquencement lore)."""
        _, _, _, cid = C.ATELIERS[idx]
        if cid is None:
            return True  # non-CTF toujours accessible
        ctf_idxs = [i for i, (_, _, _, c) in enumerate(C.ATELIERS) if c]
        try:
            pos = ctf_idxs.index(idx)
        except ValueError:
            return True
        if pos == 0:
            return True  # premier CTF toujours accessible
        prev_cid = C.ATELIERS[ctf_idxs[pos - 1]][3]
        return bool(store.get("ctf", prev_cid, False))

    def _draw_home(self):
        n              = len(C.ATELIERS)
        idx            = self.atelier_idx
        label, icon, _, cid = C.ATELIERS[idx]
        solved         = bool(cid and store.get("ctf", cid, False))
        locked         = not self._is_unlocked(idx)
        done, n_ctf    = self._ctf_count()
        ox, oy         = self._ox, self._oy

        hw.oled.fill(0)
        ui.header("ESIEA TOY", "%d/%d" % (done, n_ctf))

        # Cartes latérales avec parallaxe réduit
        for delta, sx in ((-1, 4), (1, 92)):
            side_idx = (idx + delta) % n
            _, side_icon, _, _ = C.ATELIERS[side_idx]
            side_locked = not self._is_unlocked(side_idx)
            ui.rrect(sx + ox // 2, 16 + oy // 2, 32, 20, 1)
            if side_locked:
                ui.draw_sprite("lock", sx + 12 + ox // 2, 20 + oy // 2)
            else:
                ui.draw_icon(side_icon, sx + 8 + ox // 2, 18 + oy // 2)

        # Carte centrale double bordure
        ui.rrect(43 + ox, 13 + oy, 42, 26, 1)
        ui.rrect(44 + ox, 14 + oy, 40, 24, 1)
        if locked:
            ui.draw_sprite("lock", 60 + ox, 21 + oy)
        else:
            ui.draw_icon(icon, 56 + ox, 17 + oy)

        if solved:
            hw.oled.fill_rect(75 + ox, 15 + oy, 8, 8, 1)
            ui.draw_sprite("check", 75 + ox, 15 + oy, 0)

        # Label avec scroll automatique
        lbl  = _clean(label)
        tok  = time.ticks_ms() // 200
        disp = ui.scroll_label(lbl, 14, tok) if len(lbl) > 14 else lbl
        hw.oled.text(disp, hw.cx(disp), 41, 1)

        # Points de pagination
        dot_w = n * 9
        dot_x = (hw.W - dot_w) // 2
        for i in range(n):
            px = dot_x + i * 9 + 3
            if i == idx:
                hw.oled.fill_rect(px - 1, 51, 3, 3, 1)
            else:
                hw.oled.pixel(px, 52, 1)

        if locked:
            ui.footer("Progres", "Verr.")
        else:
            ui.footer("Progres", "Lancer")
        hw.oled_show()

    def _show_progress(self):
        hw.oled.fill(0)
        ui.header("PROGRESSION")
        cy = ui.CTY() + 1
        done = 0
        ctf_entries = [(l, c) for l, _, _, c in C.ATELIERS if c]
        for i, (lbl, cid) in enumerate(ctf_entries):
            ok = bool(store.get("ctf", cid, False))
            if ok: done += 1
            mark = "[X]" if ok else "[ ]"
            hw.oled.text(("%s %s" % (mark, _clean(lbl)))[:16], 2, cy + i * 9, 1)
        n_ctf = len(ctf_entries)
        ui.hbar(2, cy + n_ctf * 9 + 2, 124, 5, done, n_ctf)
        pct = "%d/%d ateliers" % (done, n_ctf)
        hw.oled.text(pct, hw.cx(pct), cy + n_ctf * 9 + 11, 1)
        ui.footer("Retour")
        hw.oled_show()
        hw.wait_btn(8000)
        self._redraw = True

    # ── PUZZLE ────────────────────────────────────────────────────────────────

    def _enter_puzzle(self, idx):
        self.atelier_idx     = idx
        label, icon, mod, _ = C.ATELIERS[idx]

        for frame in range(7):
            hw.oled.fill(0)
            ui.header(_clean(label), "LANCEMENT")
            s = 16 + frame * 6
            ui.rrect((hw.W - s) // 2, (hw.H - s) // 2, s, s, 1)
            ui.draw_icon(icon, 56, 22)
            hw.oled_show()
            time.sleep_ms(30)

        gc.collect()
        full_mod = "apps." + mod
        try:
            # Vider le cache pour forcer le rechargement
            for _k in list(sys.modules.keys()):
                if _k == full_mod or _k == mod:
                    del sys.modules[_k]

            # __import__ avec fromlist non-vide retourne le sous-module en MicroPython
            m = __import__(full_mod, None, None, [mod])

            # Fallback : certaines versions MP retournent le paquet parent
            if not hasattr(m, "run"):
                m = (sys.modules.get(full_mod)
                     or sys.modules.get(mod)
                     or getattr(m, mod, None))

            if m is None or not hasattr(m, "run"):
                ui.message("ERREUR", mod + ": pas de run()", 2000)
            else:
                m.run()
        except Exception as err:
            print("[GM] puzzle", mod, "erreur:", err)
            ui.crash_screen(str(err))

        gc.collect()
        hw.touch()
        hw.led_off()

        done, n_ctf = self._ctf_count()
        if done == n_ctf:
            self._go(STATE_VICTORY)
        else:
            self._go(STATE_HOME)

    # ── VICTORY ───────────────────────────────────────────────────────────────

    def _enter_victory(self):
        hw.led_off()
        ui.victory("MISSION OK !", "ESIEA TOY 2026", "Temps maîtrise!")
        ui.story_pages("EPILOGUE", self._VICTORY_PAGES)
        store.put("os", "first_boot", True)
        store.save()
        self._go(STATE_HOME)

    # ── Mode Développeur (Konami Code) ────────────────────────────────────────

    def _activate_dev_mode(self):
        """Déverrouille tous les ateliers CTF via le Konami code."""
        for _, _, _, cid in C.ATELIERS:
            if cid:
                store.put("ctf", cid, True)
        store.save()

        hw.melody(C.SND_DEV)
        for _ in range(4):
            for col in (hw.led_red, hw.led_green, hw.led_blue, hw.led_yellow):
                col(); time.sleep_ms(55)
        hw.led_off()

        hw.oled.fill(0)
        ui.header("MODE DEV !")
        cy = ui.CTY() + 4
        hw.oled.text("KONAMI CODE !", hw.cx("KONAMI CODE !"), cy, 1)
        hw.oled.text("Tous ateliers", hw.cx("Tous ateliers"), cy + 12, 1)
        hw.oled.text("deverrouilles !", hw.cx("deverrouilles !"), cy + 22, 1)
        ui.draw_sprite("skull8", 12, cy + 4)
        ui.draw_sprite("skull8", hw.W - 20, cy + 4)
        ui.footer("OK")
        hw.oled_show()
        hw.wait_btn(4000)
        self._redraw = True

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _ctf_count(self):
        """Retourne (résolus, total) en ignorant les entrées sans ctf_id."""
        ctf = [(l, c) for l, _, _, c in C.ATELIERS if c]
        done = sum(1 for _, c in ctf if store.get("ctf", c, False))
        return done, len(ctf)


# ── Nettoyage ASCII (sans dépendance à ui) ────────────────────────────────────
def _clean(text):
    _MAP = {
        '\xe9':'e','\xe8':'e','\xea':'e','\xeb':'e',
        '\xe0':'a','\xe2':'a','\xe4':'a',
        '\xee':'i','\xef':'i',
        '\xf4':'o','\xf6':'o',
        '\xfb':'u','\xf9':'u','\xfc':'u',
        '\xe7':'c',
        '\xc9':'E','\xc8':'E','\xca':'E',
        '\xc0':'A','\xc2':'A','\xc7':'C',
        '\xce':'I','\xdb':'U','\xd4':'O',
    }
    result = []
    for ch in str(text):
        if ord(ch) < 128:
            result.append(ch)
        else:
            result.append(_MAP.get(ch, '?'))
    return "".join(result)
