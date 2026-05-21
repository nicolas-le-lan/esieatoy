# =============================================================================
# puzzles/indice.py — App pour lire son indice personnel
# =============================================================================
from core import hw, ui, store
import config as C
import time

CID = None

PERSONNAGES = [
    ("Jack (Morse)",    "Ecoute bien les\nbips. Les courts\net les longs ne\nsont pas pareils.", "morse"),
    ("Anne (Morse)",    "Il faut savoir\nlire le code\nmorse pour\ncomprendre le message.", "morse"),
    ("William (Cesar)", "Les lettres sont\ntoutes decalees\ndu meme nombre\nde crans.", "cesar"),
    ("Mary (Cesar)",    "Cherche le bon\ndecalage. Quand\nle texte a du\nsens, c est gagne.", "cesar"),
    ("Henry (Radar)",   "La couleur de\nla LED indique\nsi tu te\nrapproches ou non.", "radio_dist"),
    ("Charles (Radar)", "Stabilise la\ntablette dans\nla bonne zone\npour ouvrir le portail.", "radio_dist"),
]

def run():
    idx = store.get("os", "perso_idx", 0)
    
    while True:
        nom, indice, _ = PERSONNAGES[idx]
        
        hw.oled.fill(0)
        ui.header("PERSONNAGE", "INDICE")
        cy = ui.CTY()
        
        hw.oled.text("< " + nom + " >", hw.cx("< " + nom + " >"), cy + 2, 1)
        
        # Affichage de l'indice sur plusieurs lignes
        lignes = indice.split('\n')
        for i, ligne in enumerate(lignes):
            hw.oled.text(ligne, hw.cx(ligne), cy + 18 + (i * 9), 1)
            
        ui.footer("Quitter", "Choisir")
        hw.oled_show()
        
        b = hw.wait_btn(100)
        if b == "b":
            # Quitter l'application
            return
        elif b == "a":
            # Confirmer la sélection du perso
            store.put("os", "perso_idx", idx)
            store.save()
            hw.melody(C.SND_OK)
            ui.message("SAUVEGARDE", nom + "\nselectionne !", 1500)
            return
        elif b in ("lt", "up"):
            idx = (idx - 1) % len(PERSONNAGES)
            hw.melody(C.SND_NAV)
        elif b in ("rt", "dn"):
            idx = (idx + 1) % len(PERSONNAGES)
            hw.melody(C.SND_NAV)
