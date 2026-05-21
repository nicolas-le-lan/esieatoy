# =============================================================================
# core/store.py — Persistance JSON sur flash
# =============================================================================
# Toutes les données utilisateur (progression CTF, réglages, état OS) sont
# sauvegardées dans /store.json. Le module gère un cache en mémoire avec
# écriture différée (dirty flag) pour limiter l'usure de la flash.
# =============================================================================
import json, os

_FILE  = "/store.json"
_DIRTY = False
_CACHE = None

# Valeurs par défaut — fusionnées avec les données lues sur la flash
_DEFAULTS = {
    "os":      {"first_boot": True, "app": 0},
    "sys":     {"oled": "auto", "pwr_mode": "bat"},  # bat = défaut sécurisé batterie
    "sound":   {"on": True, "volume": 2},
    "display": {"sleep_ms": 60000},
    "ctf":     {},
}

def _merge(base, override):
    """Fusion récursive : les clés de override écrasent base."""
    result = dict(base)
    for k, v in override.items():
        if isinstance(result.get(k), dict) and isinstance(v, dict):
            result[k] = _merge(result[k], v)
        else:
            result[k] = v
    return result

def _load():
    global _CACHE
    try:
        with open(_FILE) as f:
            _CACHE = _merge(_DEFAULTS, json.load(f))
    except:
        _CACHE = {k: dict(v) for k, v in _DEFAULTS.items()}

def save():
    """Écrit le cache sur la flash. No-op si rien n'a changé."""
    global _DIRTY
    if not _DIRTY:
        return True
    try:
        with open(_FILE, "w") as f:
            json.dump(_CACHE, f)
        _DIRTY = False
        return True
    except Exception as e:
        print("[store] save error:", e)
        return False

def get(section, key=None, default=None):
    """
    Lit une valeur.
    get("ctf", "simon", False)  → valeur de ctf.simon
    get("ctf")                  → dict entier de la section ctf
    """
    if _CACHE is None:
        _load()
    if key is None:
        return _CACHE.get(section, default)
    return _CACHE.get(section, {}).get(key, default)

def put(section, key, value):
    """Écrit une valeur et lève le dirty flag si elle a changé."""
    global _DIRTY
    if _CACHE is None:
        _load()
    current = _CACHE.get(section, {}).get(key)
    if current != value:
        _CACHE.setdefault(section, {})[key] = value
        _DIRTY = True

def reset():
    """Efface toutes les données (reset usine)."""
    global _CACHE, _DIRTY
    _CACHE = {k: dict(v) for k, v in _DEFAULTS.items()}
    _DIRTY = True
    try:
        os.remove(_FILE)
    except:
        pass

# Chargement automatique à l'import
_load()
