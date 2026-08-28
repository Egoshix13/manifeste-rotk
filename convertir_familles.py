"""Convertit la bibliotheque complete de l'equipement (blender/gear/) en .glb
textures, pour servir de modele PAR FAMILLE aux objets du catalogue qui n'ont
pas leur propre reference de maillage.

    blender --background --factory-startup --python navigateur_cosmetiques/convertir_familles.py

POURQUOI UNE DEUXIEME SOURCE

`convertir_3d.py` ne convertit que les objets dont la table du jeu donne un
`MODEL_NAME` a EUX -- la plupart des reskins (armes ET vetements) n'en ont
pas. Mais `blender/gear/` contient deja tout l'equipement de BASE du jeu,
extrait et indexe des le debut de ce projet (chantier skins, pas celui-ci) :
armes, casques, hauts, bas, gants, kevlar. Ce sont les memes pieces que
possedent tous les reskins qui n'ont pas leur propre maillage -- l'icone le
confirme : plusieurs objets du catalogue partagent EXACTEMENT le meme
fichier icone qu'un autre, donc la meme apparence.

Reprend chaque `blender/gear/<categorie>/index.csv`, deja la ou `mesh` et
`couleur` sont apparies -- pas de nouvelle extraction depuis les archives,
juste la conversion avec materiau bake que `convert_gear.py` (celui du
chantier skins) n'applique pas.
"""
import csv
import os
import sys

import bpy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'blender'))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from preview import build_mesh, build_material                   # noqa: E402
from dds2png import dds2png                                      # noqa: E402

GEAR = os.path.join(ROOT, 'blender', 'gear')
CATEGORIES = ['arme', 'casque', 'haut', 'bas', 'gants', 'kevlar']
ICI = os.path.dirname(os.path.abspath(__file__))
SORTIE = os.path.join(ICI, 'modeles3d')
PNG_CACHE = os.path.join(ICI, 'brut3d', 'texture')


def main():
    os.makedirs(SORTIE, exist_ok=True)
    os.makedirs(PNG_CACHE, exist_ok=True)

    lignes = []
    for cat in CATEGORIES:
        src = os.path.join(GEAR, cat)
        chemin_index = os.path.join(src, 'index.csv')
        if not os.path.exists(chemin_index):
            print('%-8s index.csv absent, ignore' % cat)
            continue
        with open(chemin_index, encoding='utf-8') as f:
            for l in csv.DictReader(f):
                l['_src'] = src
                lignes.append(l)
    print('%d lignes a convertir, toutes categories confondues' % len(lignes))

    faits, ok, echecs = set(), 0, []
    for l in lignes:
        mesh = l['mesh']
        if not mesh or mesh in faits:
            continue
        faits.add(mesh)
        couleur = (l['couleur'] or '').split(';')[0].strip()
        nom_sortie = os.path.splitext(mesh)[0] + '.glb'
        cible = os.path.join(SORTIE, nom_sortie)
        if os.path.exists(cible):
            ok += 1
            continue

        src_mesh = os.path.join(l['_src'], 'mesh', mesh)
        if not os.path.exists(src_mesh):
            echecs.append((mesh, 'mesh absent du dossier source'))
            continue

        try:
            bpy.ops.wm.read_factory_settings(use_empty=True)
            obj = build_mesh(src_mesh)

            if couleur:
                src_dds = os.path.join(l['_src'], 'texture', couleur)
                if os.path.exists(src_dds):
                    png = os.path.join(PNG_CACHE,
                                       os.path.splitext(couleur)[0] + '.png')
                    if not os.path.exists(png):
                        dds2png(src_dds, png)
                    mat = build_material(obj, png, None, None, flip_green=False)
                    obj.data.materials.append(mat)

            bpy.ops.export_scene.gltf(
                filepath=cible, export_format='GLB',
                export_apply=True, export_materials='EXPORT',
                use_visible=False)
            ok += 1
        except Exception as e:
            echecs.append((mesh, str(e)))

    print('\n%d convertis (dont deja presents), %d echecs' % (ok, len(echecs)))
    for mesh, err in echecs:
        print('  %-40s %s' % (mesh, err))
    print('-> %s' % SORTIE)


if __name__ == '__main__':
    main()
