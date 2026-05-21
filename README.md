# ESIEAtoy OS

OS embarqué pour la carte **ESIEAtoy v2 Rev.A** (ESP32-C3 + MicroPython).

---

## Démarrage rapide

```bash
pip install mpremote
cd esieatoy_os
python flash.py          # détecte le port automatiquement
python flash.py COM5     # ou forcer le port
```

Après le flash, **débranche et rebranche** la carte (ou allume avec les piles).

---

## Connexion

| Méthode | Valeur |
|---------|--------|
| Wi-Fi SSID | `ESIEAtoy_XXXXXX` (unique, affiché au boot) |
| Mot de passe | `pirateXXXX` (affiché au boot) |
| Interface web | http://192.168.4.1 |
| API REST | http://192.168.4.1/api |

Le SSID et le mot de passe sont **générés automatiquement** à partir de l'adresse MAC.
Plusieurs ESIEAtoy dans la même pièce auront des réseaux différents.

---

## Structure du projet

```
esieatoy_os/
│
├── flash.py          ← Script PC pour flasher la carte
├── README.md         ← Ce fichier
│
├── config.py         ← Toutes les constantes (broches, sons, timeouts)
├── hw.py             ← Matériel (LED, buzzer, OLED, boutons, veille)
├── store.py          ← Config persistante JSON (/store.json)
├── net.py            ← Wi-Fi AP/STA + Bluetooth BLE
├── ui.py             ← Primitives OLED (menus, toggles, saisie texte)
├── notif.py          ← Notifications overlay depuis l'API
├── accel.py          ← Driver accéléromètre LIS3DH
├── runner.py         ← Exécution de code à distance
├── web.py            ← Serveur HTTP REST
├── dashboard.html    ← Interface web (streamée depuis la flash)
├── boot.py           ← Splash screen
├── main.py           ← Carrousel OS + boucle principale
│
└── apps/
    ├── __init__.py
    ├── simon.py      ← Jeu Simon Pirate (CTF)
    ├── accel_app.py  ← Balle accéléromètre
    ├── info.py       ← Informations de connexion
    ├── settings.py   ← Paramètres (Wi-Fi / BT / Son / Affichage)
    └── diag.py       ← Diagnostic matériel
```

---

## Matériel — Broches confirmées

| Composant | GPIO | Notes |
|-----------|------|-------|
| OLED SDA | 3 | I2C |
| OLED SCL | 10 | I2C |
| LED Rouge | 20 | Anode commune (LOW=allumé) |
| LED Verte | 8 | Anode commune |
| LED Bleue | 7 | Anode commune |
| Buzzer | 21 | PWM |
| Bouton UP | 0 | PULL_DOWN, actif HIGH |
| Bouton DOWN | 1 | PULL_DOWN, actif HIGH |
| Bouton LEFT | 2 | PULL_DOWN, actif HIGH |
| Bouton RIGHT | 4 | PULL_DOWN, actif HIGH |
| Bouton A | 5 | PULL_DOWN, actif HIGH |
| Bouton B | 6 | PULL_DOWN, actif HIGH |
| Accéléromètre | 0x18/0x19 | LIS3DH I2C |

**Alimentation :** USB-C ou 2 piles AAA.
Sur batterie, la puissance Wi-Fi est réduite (txpower=8dBm) pour éviter les resets.

---

## Ajouter une application

1. Créer `apps/mon_app.py` :
```python
import hw, ui

def run():
    while True:
        ui.screen("Mon App", ["Ligne 1", "Ligne 2"])
        if hw.wait_btn() == "b":
            return
```

2. L'enregistrer dans `main.py` :
```python
APPS = [
    ...
    ("Mon App", "M", "mon_app"),
]
```

3. Uploader via l'interface web (onglet Fichiers → Upload) ou :
```bash
mpremote connect COM5 cp apps/mon_app.py :apps/mon_app.py
```

---

## API REST

```bash
# Infos système
curl http://192.168.4.1/api/system

# Lister les fichiers
curl http://192.168.4.1/api/files

# Exécuter du code
curl -X POST http://192.168.4.1/api/exec \
     -H "Content-Type: application/json" \
     -d '{"code":"import gc; print(gc.mem_free())"}'

# Lancer une app
curl -X POST http://192.168.4.1/api/run/apps/simon.py

# Réseau
curl http://192.168.4.1/api/network

# Notif OLED
curl -X POST http://192.168.4.1/api/notif \
     -H "Content-Type: application/json" \
     -d '{"msg":"Bravo !", "duration": 3000}'

# Accéléromètre
curl http://192.168.4.1/api/accel
```

---

## Navigation carte

| Bouton | Action |
|--------|--------|
| ← / → | Naviguer dans le carrousel |
| A | Lancer l'app sélectionnée |
| B (menu) | Veille écran |
| B (dans app) | Retour au menu |
