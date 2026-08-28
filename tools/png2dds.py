"""Reencode un PNG en .dds (via nvcompress, NVIDIA Texture Tools).

Usage: python tools/png2dds.py <in.png> <out.dds>

`png2dds` : BC1 (DXT1) sans alpha -- le format des cartes couleur du jeu.
`png2dds_bc3` : BC3 (DXT5), pour les cartes a 4 canaux (_N, _S).
"""
import os, subprocess, sys, struct

NVCOMPRESS = r'C:\Program Files\NVIDIA Corporation\NVIDIA Texture Tools\nvcompress.exe'

# Meme précaution que dds2png : sans ce drapeau, chaque compression fait
# clignoter une fenetre de console derriere ManifesteROTK (compile
# --windowed, donc sans console a laquelle rattacher le sous-processus).
_SANS_FENETRE = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0


def png2dds(src, dst):
    r = subprocess.run([NVCOMPRESS, '-bc1', '-noalpha', '-production', '-silent',
                        os.path.abspath(src), os.path.abspath(dst)],
                       capture_output=True, text=True, creationflags=_SANS_FENETRE)
    if not os.path.exists(dst):
        raise RuntimeError(f'echec compression {src}: {r.stdout}{r.stderr}')
    return dst


def png2dds_bc3(src, dst, normal_map=False):
    """BC3 (DXT5), pour les cartes _N et _S -- elles ont besoin de leurs
    4 canaux, BC1 n'en garde que 3 sans alpha.

    `normal_map=True` bascule sur `-bc3n`. A EVITER pour ce projet : verifie
    a l'usage que ce mode reinterprete la SOURCE comme une normale standard
    (X,Y dans rouge/vert) et reencode lui-meme vers alpha/vert au moment de
    compresser. Nos PNG source ont DEJA ce remap fait a la main -- les deux
    se cumulent et le resultat observe est un motif en damier sur toute la
    texture. BC3 simple copie les 4 canaux tels quels."""
    r = subprocess.run([NVCOMPRESS, '-bc3n' if normal_map else '-bc3',
                        '-production', '-silent',
                        os.path.abspath(src), os.path.abspath(dst)],
                       capture_output=True, text=True, creationflags=_SANS_FENETRE)
    if not os.path.exists(dst):
        raise RuntimeError(f'echec compression {src}: {r.stdout}{r.stderr}')
    return dst


def header(path):
    d = open(path, 'rb').read(128)
    size, flags, h, w, pitch, depth, mips = struct.unpack_from('<7I', d, 4)
    pfflags, fourcc = struct.unpack_from('<I4s', d, 0x50)
    return dict(flags=flags, w=w, h=h, mips=mips, fourcc=fourcc.decode('ascii', 'replace'),
                pfflags=pfflags, taille=os.path.getsize(path))


if __name__ == '__main__':
    out = png2dds(sys.argv[1], sys.argv[2])
    print(f'OK -> {out}')
    print('   ', header(out))
