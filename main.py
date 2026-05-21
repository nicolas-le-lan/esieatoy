# main.py — ESIEA TOY OS · Point d'entrée principal

# ── Fréquence CPU sécurisée AVANT tout import ─────────────────────────────────
# Sans ça, l'ESP32-C3 démarre à 160 MHz par défaut.
# Sur batterie (2× AAA ≈ 3 V) le pic de courant au boot peut déclencher
# le brownout-reset avant même que le premier écran s'affiche.
import machine
machine.freq(80_000_000)

import gc
gc.collect()

try:
    from core.game_manager import GameManager
    GameManager().run()
except Exception as e:
    try:
        from core import hw
        hw.oled.fill(0)
        hw.oled.text("!! BOOT FATAL !!", 0, 10, 1)
        msg = str(e)
        for i, chunk in enumerate([msg[j:j+16] for j in range(0, min(48, len(msg)), 16)]):
            hw.oled.text(chunk, 0, 22 + i * 11, 1)
        hw.oled.text("Reset = RST btn", 0, 55, 1)
        hw.oled_show()
        hw.led_red()
        hw.wait_btn(30000)
        hw.led_off()
    except:
        print("[MAIN FATAL]", e)
    machine.reset()
