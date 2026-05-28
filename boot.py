# boot.py — ESIEA TOY OS · Point d'entrée boot rapide
import gc, sys
for p in ("/", ""):
    if p not in sys.path:
        sys.path.insert(0, p)
gc.collect()
