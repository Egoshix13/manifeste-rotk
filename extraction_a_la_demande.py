"""Extraction a la demande : le maillage et TOUTES les textures d'un objet,
depuis le jeu installe sur cette machine, en un clic depuis l'appli.

CE QUE CA DONNE, ET CE QUI LE DISTINGUE DES APERCUS

`convertir_3d.py` ne gardait que la texture COULEUR, pour un aperçu 3D
rapide. Ici c'est l'inverse : on veut TOUT ce qu'un skinner reprend pour
travailler -- couleur, normale, speculaire, chaque carte que l'`.adr`
declare -- dans leur format brut du jeu (`.dme`, `.dds`), plus une version
`.png` de chaque texture pour les regarder sans outil special. C'est le
meme point de depart que celui utilise a la main pour le hoodie, en debut
de ce projet.

NE MARCHE QUE SUR UNE MACHINE AVEC LE JEU INSTALLE

Les archives sources (`C:\\Games\\ROTK\\Resources\\Assets`, plusieurs
gigaoctets) ne voyagent pas avec l'appli distribuee -- seuls les .glb et
.png deja convertis le font. Ce module echoue proprement, avec un message
clair, si le dossier du jeu est introuvable.
"""
import glob
import os
import re
import struct
import sys
import tempfile
import threading

# pack2/dds2png : copie embarquee dans tools/ a cote de ce fichier (celle
# que le depot Git et le build GitHub Actions connaissent), avec repli sur
# SKINHA/tools pour les autres scripts du depot parent.
ICI_MODULE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(ICI_MODULE)
sys.path.insert(0, os.path.join(ROOT, 'tools'))
sys.path.insert(0, os.path.join(ICI_MODULE, 'tools'))
from pack2 import Pack2, crc64                                   # noqa: E402

RACINES_JEU = [r"C:\Games\ROTK",
              r"C:\Program Files (x86)\Steam\steamapps\common\H1Z1"]

# Chemin choisi par l'utilisateur dans l'interface (engrenage), prioritaire
# sur les deux emplacements par defaut. Persiste par le lanceur dans
# chemin_jeu.txt a cote de l'executable, pas ici.
_RACINE_PERSO = None

_INDEX = None  # construit une fois, reutilise a chaque extraction
# Le lanceur prechauffe l'index dans un thread de fond au demarrage ; le
# verrou evite qu'un clic precoce sur "Extraire" le construise en double.
_VERROU_INDEX = threading.Lock()


def definir_racine_perso(chemin):
    """Change le dossier du jeu et invalide l'index (a reconstruire sur le
    nouveau chemin). `None` ou vide : retour aux emplacements par defaut."""
    global _RACINE_PERSO, _INDEX
    with _VERROU_INDEX:
        _RACINE_PERSO = chemin or None
        _INDEX = None


def ressemble_au_jeu(chemin):
    """Le dossier contient-il des archives .pack2 ? Parcours limite en
    profondeur : verifier, pas indexer -- un mauvais chemin (C:\\ entier...)
    ne doit pas geler l'interface."""
    for base, dossiers, fichiers in os.walk(chemin):
        if any(f.lower().endswith('.pack2') for f in fichiers):
            return True
        if base[len(chemin):].count(os.sep) >= 3:
            dossiers[:] = []
    return False


def jeu_installe():
    racines = ([_RACINE_PERSO] if _RACINE_PERSO else []) + RACINES_JEU
    return next((d for d in racines if os.path.isdir(d)), None)


def precharger_index():
    """Construit l'index en avance -- a lancer dans un thread au demarrage
    pour que le premier clic sur "Extraire" ne paraisse pas gele le temps
    de parcourir tous les .pack2 du jeu."""
    _index()


def _index():
    global _INDEX
    with _VERROU_INDEX:
        if _INDEX is not None:
            return _INDEX
        jeu = jeu_installe()
        if jeu is None:
            return None
        table, packs = {}, {}
        for a in sorted(glob.glob(os.path.join(jeu, '**', '*.pack2'), recursive=True)):
            # struct.error : archive tronquee ou corrompue -- l'ignorer
            # plutot que de faire tomber tout l'index (et avec lui le
            # thread de prechauffage au demarrage).
            try:
                p = Pack2(a)
            except (ValueError, OSError, struct.error):
                continue
            packs[a] = p
            for e in p.assets:
                table.setdefault(e[0], (a, e))
        _INDEX = (table, packs)
        return _INDEX


def _lire(nom):
    idx = _index()
    if idx is None:
        return None
    table, packs = idx
    v = table.get(crc64(nom))
    if v is None:
        return None
    a, e = v
    return packs[a].read(e)


def _variantes(nom):
    """Meme correction que extraire_3d.py -- <gender> non substitue,
    singulier/pluriel Weapon(s)_ incoherent dans la table du jeu."""
    out = []
    if '<gender>' in nom:
        out += [nom.replace('<gender>', 'Male'), nom.replace('<gender>', 'Female')]
    if nom.startswith('Weapon_') and not nom.startswith('Weapons_'):
        out.append('Weapons_' + nom[len('Weapon_'):])
    elif nom.startswith('Weapons_'):
        out.append('Weapon_' + nom[len('Weapons_'):])
    return out


def extraire(nom_adr, dossier_sortie):
    """Ecrit mesh + toutes les textures de `nom_adr` dans `dossier_sortie`.

    Retourne (ok: bool, message: str, fichiers: list[str]).
    """
    if jeu_installe() is None:
        return False, ("Jeu introuvable sur cette machine (ni C:\\Games\\ROTK "
                       "ni le dossier Steam). Installe ailleurs ? Indiquez "
                       "son dossier via l'engrenage en haut de la fenetre. "
                       "L'extraction a la demande a besoin des fichiers du "
                       "jeu, contrairement aux apercus livres avec l'appli."), []

    d = _lire(nom_adr)
    nom_reel = nom_adr
    if d is None:
        for v in _variantes(nom_adr):
            d = _lire(v)
            if d is not None:
                nom_reel = v
                break
    if d is None:
        return False, '%s introuvable dans les archives du jeu.' % nom_adr, []

    m = re.search(rb'Base fileName="([^"]+)"', d)
    if not m:
        return False, '%s ne declare pas de maillage.' % nom_reel, []
    mesh = m.group(1).decode()
    textures = sorted(set(t.decode() for t in
                          re.findall(rb'textureName="([^"]+)"', d)))
    textures = [t for t in textures if t.lower() not in
               ('white.dds', 'black.dds', 'grey.dds', 'detail_cube.dds')]

    mesh_data = _lire(mesh)
    if mesh_data is None:
        return False, 'Maillage %s introuvable.' % mesh, []

    os.makedirs(dossier_sortie, exist_ok=True)
    fichiers = []

    with open(os.path.join(dossier_sortie, mesh), 'wb') as f:
        f.write(mesh_data)
    fichiers.append(mesh)

    manquantes = []
    for t in textures:
        d2 = _lire(t)
        if d2 is None:
            manquantes.append(t)
            continue
        with open(os.path.join(dossier_sortie, t), 'wb') as f:
            f.write(d2)
        fichiers.append(t)

        # Version .png a cote, si l'outil de conversion est disponible --
        # jamais bloquant : la .dds brute suffit pour Blender.
        try:
            from dds2png import dds2png
            png = os.path.join(dossier_sortie, os.path.splitext(t)[0] + '.png')
            dds2png(os.path.join(dossier_sortie, t), png)
            fichiers.append(os.path.basename(png))
        except Exception:
            pass

    msg = '%d fichiers extraits (%s).' % (len(fichiers), nom_reel)
    if manquantes:
        msg += ' %d texture(s) introuvable(s) : %s' % (
            len(manquantes), ', '.join(manquantes))
    return True, msg, fichiers
