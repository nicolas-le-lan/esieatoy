# =============================================================================
# apps/simon.py — Atelier 3 : LE SIMON (sécurité cognitive)
# =============================================================================
# STORY : Un verrou de sécurité temporel s'active sur la tablette.
#         Pour le court-circuiter et continuer, vous devez répéter une série
#         de signaux lumineux et sonores.
# BOUTONS :
#   UP    -> ROUGE (880 Hz)
#   DOWN  -> VERT (660 Hz)
#   LEFT  -> BLEU (554 Hz)
#   RIGHT -> JAUNE (440 Hz)
#   B     -> Quitter la séquence
# =============================================================================
from core import hw, ui, store
import config as C
import time

try:
    import random
except ImportError:
    from core import rand as random

CID = "simon"
TARGET_LEVEL = 5  # Atteindre 5 répétitions correctes de suite pour gagner

# Mappage des boutons
BUTTONS = ["up", "dn", "lt", "rt"]

# Paramètres des étapes : (Led_func, freq, x, y, w, h, label)
PADS = {
    "up": (hw.led_red, 880, 58, 16, 12, 10, "^"),
    "dn": (hw.led_green, 660, 58, 38, 12, 10, "v"),
    "lt": (hw.led_blue, 554, 44, 27, 12, 10, "<"),
    "rt": (hw.led_yellow, 440, 72, 27, 12, 10, ">")
}

_INTRO = [
    "Soudain, l'ecran\nse bloque ! Un\nverrou de securite\ntemporel s'active.",
    "Pour le contourner,\nvous devez repeter\nles signaux emis\npar la tablette.",
    "Un test de memoire\net de reflexes !",
    "UP    = ROUGE\nDOWN  = VERT\nLEFT  = BLEU\nRIGHT = JAUNE\nB = quitter",
]

def _draw_pad(pad_key, active=False):
    led_fn, freq, x, y, w, h, lbl = PADS[pad_key]
    if active:
        hw.oled.fill_rect(x, y, w, h, 1)
        hw.oled.text(lbl, x + (w - 8) // 2, y + (h - 8) // 2, 0)
    else:
        ui.rrect(x, y, w, h, 1)
        hw.oled.text(lbl, x + (w - 8) // 2, y + (h - 8) // 2, 1)

def _draw_screen(level, state_msg="MEMOIRE"):
    hw.oled.fill(0)
    ui.header("VERROU SIMON", "%d/%d" % (level, TARGET_LEVEL))
    cy = ui.CTY()
    
    # Dessiner les 4 pads
    for k in PADS:
        _draw_pad(k, active=False)
        
    hw.oled.text(state_msg, hw.cx(state_msg), cy + 32, 1)
    ui.footer("Quitter", None)
    hw.oled_show()

def _play_step(btn, duration=350):
    led_fn, freq, _, _, _, _, _ = PADS[btn]
    
    # Rendre actif sur l'écran
    hw.oled.fill(0)
    ui.header("VERROU SIMON")
    for k in PADS:
        _draw_pad(k, active=(k == btn))
    ui.footer("Quitter", None)
    hw.oled_show()
    
    # Son et LED
    led_fn()
    hw.tone(freq, duration)
    hw.led_off()
    
    # Pause et retour à l'écran de base
    time.sleep_ms(80)
    
def run():
    if store.get("ctf", CID, False):
        if not ui.confirm("DEJA RESOLU", "Rejouer cet atelier ?"):
            return

    if not ui.story_pages("SECURITE", _INTRO):
        return

    # Générer la séquence complète à l'avance
    sequence = [random.choice(BUTTONS) for _ in range(TARGET_LEVEL)]
    
    current_length = 1
    
    while current_length <= TARGET_LEVEL:
        # Phase 1 : Affichage de la séquence par la machine
        _draw_screen(current_length - 1, "ECOUTER...")
        time.sleep_ms(600)
        
        for i in range(current_length):
            _play_step(sequence[i], duration=350 - current_length * 15) # accélère légèrement
            
        # Phase 2 : Entrée du joueur
        _draw_screen(current_length - 1, "A VOUS !")
        
        player_step = 0
        failed = False
        
        while player_step < current_length:
            btn = hw.wait_btn(0)
            if btn == "b":
                # Quitter
                return
            elif btn in BUTTONS:
                # Retenir le bouton et jouer le retour visuel/sonore
                _play_step(btn, duration=220)
                
                # Vérifier si c'est correct
                if btn == sequence[player_step]:
                    player_step += 1
                else:
                    failed = True
                    break
            else:
                # Autre touche pressée
                hw.melody(C.SND_ERR)
                failed = True
                break
                
        if failed:
            hw.led_red()
            hw.melody(C.SND_LOSE)
            ui.shake(400)
            ui.message("ECHEC !", "La sequence etait\nincorrecte !\nRecommencons...", 1500)
            hw.led_off()
            # Régénérer une nouvelle séquence
            sequence = [random.choice(BUTTONS) for _ in range(TARGET_LEVEL)]
            current_length = 1
            time.sleep_ms(200)
        else:
            hw.melody(C.SND_STEP_OK)
            time.sleep_ms(300)
            current_length += 1
            
    # Séquence de victoire
    hw.led_green()
    hw.melody(C.SND_WIN)
    store.put("ctf", CID, True)
    store.save()
    
    ui.story_pages("DEVERROUILLE !", [
        "CLAC ! Le verrou\nsymbionique cede.\nLes signaux se\nstabilisent.",
        "Un message s'affiche\ndesormais sur\nl'ecran principal :",
        "SYSTEME DEVERROUILLE\nFlux de donnees\nintercepte !",
        "Preparez-vous a\ndecoder ce code\nASCII mysterieux\npour continuer !",
    ])
    hw.led_off()
    ui.victory("SECURITE OK", "Systeme debloque !", "Atelier 3/6")
