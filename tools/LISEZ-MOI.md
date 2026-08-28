# Outils embarques

Copies de `../../tools/` (le depot SKINHA complet n'est pas publie) pour
que l'application soit compilable telle quelle -- notamment par le
workflow GitHub Actions, qui n'a acces qu'a ce depot.

- `pack2.py` : lecture des archives `.pack2` du jeu (index + extraction).
- `dds2png.py` : conversion `.dds` -> `.png` via nvdecompress (NVIDIA
  Texture Tools), avec `CREATE_NO_WINDOW` pour ne pas faire clignoter de
  console depuis l'appli.
- `dds_fixflags.py` : correction des en-tetes DDS que nvdecompress refuse.

En cas de modification cote `SKINHA/tools/`, reporter ici (et vice versa).
