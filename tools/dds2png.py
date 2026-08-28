"""Convertit un .dds ForgeLight en .png (via NVIDIA Texture Tools).

Usage: python tools/dds2png.py <in.dds> [out.png]
"""
import os, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dds_fixflags import fix_flags

NVDECOMPRESS = r'C:\Program Files\NVIDIA Corporation\NVIDIA Texture Tools\nvdecompress.exe'

# Sans ca, chaque conversion fait clignoter une fenetre de console derriere
# l'appli -- nvdecompress est un programme console, et Windows lui en cree
# une des qu'on le lance, meme quand on capture sa sortie. Invisible en
# ligne de commande (une console tourne deja), voyant depuis ManifesteROTK
# (compile --windowed, donc sans aucune console a la base).
_SANS_FENETRE = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0


def dds2png(src, dst=None):
    dst = dst or os.path.splitext(src)[0] + '.png'
    tmp = tempfile.NamedTemporaryFile(suffix='.dds', delete=False)
    tmp.close()
    try:
        fix_flags(src, tmp.name)
        r = subprocess.run([NVDECOMPRESS, '-format', 'png', tmp.name, os.path.abspath(dst)],
                           capture_output=True, text=True, creationflags=_SANS_FENETRE)
        if not os.path.exists(dst):
            raise RuntimeError(f'echec conversion {src}: {r.stdout}{r.stderr}')
    finally:
        os.unlink(tmp.name)
    return dst


if __name__ == '__main__':
    out = dds2png(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
    print(f'OK -> {out}')
