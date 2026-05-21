# =============================================================================
# core/rand.py — Générateur pseudo-aléatoire (LCG)
# =============================================================================
# MicroPython n'a pas toujours le module random complet.
# Ce module fournit les fonctions indispensables aux puzzles.
# =============================================================================
import time

_seed = time.ticks_ms() ^ 0xDEAD

def _next():
    global _seed
    _seed = (_seed * 1664525 + 1013904223) & 0xFFFFFFFF
    return _seed

def randint(a, b):
    """Entier aléatoire entre a et b inclus."""
    return a + (_next() % (b - a + 1))

def choice(seq):
    """Élément aléatoire d'une séquence."""
    return seq[_next() % len(seq)]

def shuffle(lst):
    """Mélange en place (Fisher-Yates)."""
    for i in range(len(lst) - 1, 0, -1):
        j = _next() % (i + 1)
        lst[i], lst[j] = lst[j], lst[i]
    return lst

def sample(seq, k):
    """k éléments aléatoires sans remise."""
    lst = list(seq)
    shuffle(lst)
    return lst[:k]
