"""Extrait maillage + texture couleur pour les objets qui ont un MODEL_NAME direct.

    python navigateur_cosmetiques/extraire_3d.py

CE QUI EST COUVERT, ET CE QUI NE L'EST PAS

Sur les 1885 objets du catalogue, 154 seulement (87 modeles distincts)
portent une reference directe -- `MODEL_NAME` -- vers un `.adr`, donc vers
un maillage. Ce sont presque tous des armes et des objets tenus en main.

Les 1731 autres -- la plupart des vetements, la plupart des skins d'arme,
les sacs, les skins de vehicule -- n'ont PAS de `MODEL_NAME` dans cette
table. Leur apparence passe par une indirection differente (alias de
texture pose sur un maillage de corps partage, comme pour le hoodie du
skin ROTK) : pas une extraction mecanique, un travail par categorie. Ce
script ne les couvre pas.

SORTIE

    navigateur_cosmetiques/brut3d/mesh/<Modele>.dme
    navigateur_cosmetiques/brut3d/texture/<Modele>_C.dds
    navigateur_cosmetiques/brut3d/liste.csv     modele -> mesh, texture
"""
import csv
import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from pack2 import Pack2, crc64                                   # noqa: E402

JEU = r"C:\Games\ROTK"
ICI = os.path.dirname(os.path.abspath(__file__))
BRUT = os.path.join(ICI, 'brut3d')


def index_archives():
    table, packs = {}, {}
    for a in sorted(glob.glob(os.path.join(JEU, '**', '*.pack2'), recursive=True)):
        p = Pack2(a)
        packs[a] = p
        for e in p.assets:
            table.setdefault(e[0], (a, e))
    return table, packs


def lire(table, packs, nom):
    v = table.get(crc64(nom))
    if v is None:
        return None
    a, e = v
    return packs[a].read(e)


def variantes(nom):
    """Corrections courantes vues sur les MODEL_NAME de la table d'objets --
    la table elle-meme porte des noms qui ne correspondent a AUCUN fichier
    des archives, pour deux raisons distinctes, verifiees sur les echecs :

      - `<gender>` n'est jamais substitue. Les vetements sont declares
        'Survivor<gender>_Head_Hat_Cowboy.adr' au lieu de 'SurvivorMale_...'.
        Recupere 17 des 19 corrections possibles a lui seul.
      - singulier/pluriel incoherent : 'Weapon_M16A4.adr' quand le fichier
        reel est 'Weapons_M16A4.adr'. Faute de saisie dans la table du jeu,
        pas une variation predictible -- releve au cas par cas, pas devinee.

    Ce qui ne matche toujours pas apres ces essais n'est pas une faute de
    frappe : ce sont des fichiers absents des archives, des references
    perimees vers un maillage renomme ou supprime depuis. `extraire_3d.py`
    les liste comme manquants plutot que d'inventer une troisieme regle.
    """
    out = []
    if '<gender>' in nom:
        out.append(nom.replace('<gender>', 'Male'))
        out.append(nom.replace('<gender>', 'Female'))
    if nom.startswith('Weapon_') and not nom.startswith('Weapons_'):
        out.append('Weapons_' + nom[len('Weapon_'):])
    elif nom.startswith('Weapons_'):
        out.append('Weapon_' + nom[len('Weapons_'):])
    return out


def choisir_texture_couleur(textures):
    """La texture couleur, parmi celles de l'.adr -- suffixe _C, sinon la
    premiere qui n'est ni une normale/speculaire ni un nom generique.

    Le suffixe de carte (_N, _S, _DS, _PM) n'est pas toujours en toute fin
    de nom : les jeux de textures vue-a-la-3e-personne le suivent d'un
    `_3P` ou `_1P` (`Weapon_Binoculars_N_3P.dds`). Une premiere version ne
    reconnaissait que le suffixe en fin de chaine et prenait ces normales
    pour des couleurs.
    """
    def carte(t):
        m = re.search(r'_(C|N|S|DS|PM)(?:_(?:1P|3P))?\.dds$', t, re.I)
        return m.group(1).upper() if m else None

    for t in textures:
        if carte(t) == 'C':
            return t
    for t in textures:
        if carte(t) is None and t.lower() not in (
                'white.dds', 'black.dds', 'grey.dds', 'detail_cube.dds'):
            return t
    return None


def main():
    with open(os.path.join(ICI, 'catalogue.json'), encoding='utf-8') as f:
        catalogue = json.load(f)

    modeles = sorted({o['modele'] for o in catalogue if o['modele'].strip()})
    print('%d modeles distincts a resoudre' % len(modeles))

    print('indexation des archives...')
    table, packs = index_archives()
    print('  %d archives, %d entrees' % (len(packs), len(table)))

    os.makedirs(os.path.join(BRUT, 'mesh'), exist_ok=True)
    os.makedirs(os.path.join(BRUT, 'texture'), exist_ok=True)

    lignes = []
    manques = []
    for nom_adr in modeles:
        d = lire(table, packs, nom_adr)
        nom_reel = nom_adr
        if d is None:
            for v in variantes(nom_adr):
                d = lire(table, packs, v)
                if d is not None:
                    nom_reel = v
                    break
        if d is None:
            manques.append((nom_adr, 'adr introuvable'))
            continue
        m = re.search(rb'Base fileName="([^"]+)"', d)
        if not m:
            manques.append((nom_adr, 'pas de Base fileName'))
            continue
        mesh = m.group(1).decode()
        textures = [t.decode() for t in re.findall(rb'textureName="([^"]+)"', d)]
        couleur = choisir_texture_couleur(textures)

        mesh_data = lire(table, packs, mesh)
        if mesh_data is None:
            manques.append((nom_adr, 'mesh introuvable: ' + mesh))
            continue
        open(os.path.join(BRUT, 'mesh', mesh), 'wb').write(mesh_data)

        chemin_tex = ''
        if couleur:
            tex_data = lire(table, packs, couleur)
            if tex_data is not None:
                open(os.path.join(BRUT, 'texture', couleur), 'wb').write(tex_data)
                chemin_tex = couleur
            else:
                manques.append((nom_adr, 'texture introuvable: ' + couleur))

        lignes.append((nom_adr, mesh, chemin_tex))

    for p in packs.values():
        p.close()

    with open(os.path.join(BRUT, 'liste.csv'), 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['adr', 'mesh', 'texture'])
        w.writerows(lignes)

    print('\n%d resolus, %d manques' % (len(lignes), len(manques)))
    for adr, raison in manques:
        print('  %-42s %s' % (adr, raison))
    print('-> %s' % os.path.join(BRUT, 'liste.csv'))


if __name__ == '__main__':
    main()
