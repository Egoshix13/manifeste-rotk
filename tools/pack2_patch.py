"""Remplace UN asset dans une archive .pack2, sur place.

    python tools/pack2_patch.py <archive.pack2> <NomAsset.dds> <fichier.dds>

POURQUOI SUR PLACE PLUTOT QUE RECONSTRUIRE

Reconstruire l'archive demanderait de reecrire 488 Mo et de recalculer tous
les offsets : beaucoup de surface pour se tromper, sur un fichier de jeu.

Les blocs de donnees sont alignes sur 256 octets et separes par du
remplissage, donc l'emplacement d'un asset est presque toujours plus grand
que l'asset lui-meme. Si le nouveau bloc y tient, il suffit de l'ecrire au
MEME offset et de corriger une seule entree de la table -- sa taille et son
CRC. Tout le reste du fichier ne bouge pas d'un octet.

CE QUE LA TABLE ATTEND, releve sur les archives du jeu

  - offsets multiples de 256, premier bloc a 512 ;
  - un bloc compresse commence par A1 B2 C3 D4 en big-endian, suivi de la
    taille DECOMPRESSEE en u32 big-endian, puis du flux zlib ;
  - le champ crc32 de la table porte sur le BLOC STOCKE (compresse, en-tete
    comprise), pas sur les donnees decompressees -- verifie sur plusieurs
    entrees avant d'ecrire quoi que ce soit.
"""
import os
import struct
import sys
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pack2 import Pack2, crc64

ENTRY = struct.Struct('<QQQII')


def place_disponible(p, entree):
    """Octets utilisables a partir de l'offset de `entree` : jusqu'au bloc
    suivant, ou jusqu'a la table si c'est le dernier."""
    suivants = [e[1] for e in p.assets if e[1] > entree[1]]
    return (min(suivants) if suivants else p.map_offset) - entree[1]


def patch(archive, nom_asset, source, verbose=True):
    donnees = open(source, 'rb').read()
    bloc = (struct.pack('>4sI', b'\xa1\xb2\xc3\xd4', len(donnees))
            + zlib.compress(donnees, 9))

    p = Pack2(archive)
    h = crc64(nom_asset)
    idx = next((i for i, e in enumerate(p.assets) if e[0] == h), None)
    if idx is None:
        p.close()
        sys.exit('%s : absent de %s' % (nom_asset, os.path.basename(archive)))
    entree = p.assets[idx]
    place = place_disponible(p, entree)
    map_offset, count = p.map_offset, p.count
    p.close()

    hash_, off, taille, zipped, crc = entree
    somme = zlib.crc32(bloc) & 0xffffffff

    if len(bloc) <= place:
        neuf = ENTRY.pack(hash_, off, len(bloc), 1, somme)
        with open(archive, 'r+b') as f:
            f.seek(off)
            f.write(bloc)
            f.seek(map_offset + idx * ENTRY.size)
            f.write(neuf)
        ou = off
    else:
        ou = reloge(archive, idx, entree, bloc, somme, count, map_offset)

    if verbose:
        print('%s' % nom_asset)
        print('  archive     %s' % os.path.basename(archive))
        print('  emplacement %d octets disponibles' % place)
        print('  avant       %d octets stockes' % taille)
        print('  apres       %d octets stockes (%d bruts)' % (len(bloc), len(donnees)))
        if ou == off:
            print('  offset      %d (inchange)' % off)
        else:
            print('  offset      %d -> %d (bloc reloge en fin de donnees)'
                  % (off, ou))
    return ou, len(bloc)


def reloge(archive, idx, entree, bloc, somme, count, map_offset):
    """Ecrit `bloc` la ou commencait la table, et repousse la table derriere.

    Ecraser sur place suppose que le nouveau bloc tient dans le trou du
    precedent. Quand il deborde -- ici de 5 Ko sur la speculaire du hoodie,
    parce que notre encodage DXT5 se compresse moins bien que celui d'origine
    quel que soit le reglage -- il faut lui trouver de la place ailleurs.

    Le plus simple serait d'ajouter le bloc APRES la table. Ca marcherait :
    le lecteur ne fait que se positionner a `offset`. Mais toutes les archives
    du jeu rangent les donnees d'abord et la table en dernier, et rien ne dit
    qu'aucun outil ne s'appuie sur cet ordre. On le preserve donc : le bloc
    prend la place de la table, la table repart juste derriere, alignee sur
    256 comme les blocs.

    Seules trois choses changent dans l'en-tete et la table : `file_length`,
    `map_offset`, et l'entree relogee. Les offsets de tous les autres assets
    sont intacts -- c'est ce qui distingue ce chemin d'une reconstruction.
    """
    hash_ = entree[0]
    off = map_offset
    fin = off + len(bloc)
    map_neuf = (fin + 255) // 256 * 256

    with open(archive, 'r+b') as f:
        f.seek(map_offset)
        table = bytearray(f.read(count * ENTRY.size))
        table[idx * ENTRY.size:(idx + 1) * ENTRY.size] = ENTRY.pack(
            hash_, off, len(bloc), 1, somme)

        f.seek(off)
        f.write(bloc)
        f.write(b'\0' * (map_neuf - fin))
        f.write(bytes(table))
        f.truncate()

        taille_fin = map_neuf + count * ENTRY.size
        f.seek(8)
        f.write(struct.pack('<QQ', taille_fin, map_neuf))

    return off


def verifie(archive, nom_asset, source):
    """Relit l'asset depuis l'archive patchee et le compare a la source."""
    attendu = open(source, 'rb').read()
    p = Pack2(archive)
    h = crc64(nom_asset)
    e = next(x for x in p.assets if x[0] == h)
    lu = p.read(e)
    p.close()
    ok = lu == attendu
    print('  relecture   %d octets, %s' % (len(lu), 'IDENTIQUE' if ok else 'DIFFERENT'))
    return ok


if __name__ == '__main__':
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    a, n, s = sys.argv[1:4]
    patch(a, n, s)
    verifie(a, n, s)
