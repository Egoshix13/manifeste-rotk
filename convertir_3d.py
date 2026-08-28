"""Convertit brut3d/ en .glb textures, materiau couleur inclus.

    blender --background --factory-startup --python navigateur_cosmetiques/convertir_3d.py

DIFFERENCE AVEC blender/convert_gear.py

Ce script-la exporte `export_materials='NONE'` -- le maillage et les
textures sortent comme des fichiers separes, sans lien entre eux. Ca
convient pour livrer des assets qu'on retexturera de toute facon, mais un
aperçu qu'on veut regarder tel quel sans rien reassembler a besoin du
materiau BAKE DANS le .glb. D'ou un export different, pas juste un dossier
different.

`build_mesh` et `build_material` viennent de blender/preview.py, deja
utilises pour les rendus de controle du skin -- meme decodage .dme, meme
retournement d'axes, pas une deuxieme implementation qui pourrait diverger.
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

ICI = os.path.dirname(os.path.abspath(__file__))
BRUT = os.path.join(ICI, 'brut3d')
SORTIE = os.path.join(ICI, 'modeles3d')


def main():
    os.makedirs(SORTIE, exist_ok=True)
    with open(os.path.join(BRUT, 'liste.csv'), encoding='utf-8') as f:
        lignes = list(csv.DictReader(f))

    ok, echecs = 0, []
    for l in lignes:
        adr, mesh, texture = l['adr'], l['mesh'], l['texture']
        nom_sortie = os.path.splitext(mesh)[0]
        cible = os.path.join(SORTIE, nom_sortie + '.glb')

        try:
            bpy.ops.wm.read_factory_settings(use_empty=True)
            obj = build_mesh(os.path.join(BRUT, 'mesh', mesh))

            if texture:
                src_dds = os.path.join(BRUT, 'texture', texture)
                png = os.path.join(BRUT, 'texture',
                                   os.path.splitext(texture)[0] + '.png')
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
            echecs.append((adr, str(e)))

    print('\n%d convertis, %d echecs' % (ok, len(echecs)))
    for adr, err in echecs:
        print('  %-40s %s' % (adr, err))
    print('-> %s' % SORTIE)


if __name__ == '__main__':
    main()
