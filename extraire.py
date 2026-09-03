"""Extrait le catalogue d'objets ROTK et leurs icones.

    python navigateur_cosmetiques/extraire.py

CE QUE C'EST

`ClientItemDefinitions.txt` est la table maitresse : une ligne par objet du
jeu (arme, vetement, skin, embleme...), avec sa rarete, son modele 3D, et un
`IMAGE_SET_ID` qui mene a son icone. La chaine, verifiee a la main sur un
exemple avant d'ecrire ce script :

    objet #2 (une arme)  ->  IMAGE_SET_ID 1547
                         ->  ImageSetMappings.txt  ->  image ID 1577
                         ->  Images.txt             ->  Icon_Weapon_Pistol_45Auto_745.dds

Cette .dds est une texture ordinaire dans les archives, extraite et
convertie comme n'importe quelle autre texture de ce projet.

CE QUI MANQUE : LES VRAIS NOMS

Chaque objet a un `NAME_ID`, cense mener a son nom lisible ("Casque intégral
d'assaut lourd"...) via les fichiers de langue (`Locale/fr_fr_data.dat`). Le
lien ne fonctionne pas : les NAME_ID de la table (des petits nombres, ex.
22468) ne recoupent AUCUN identifiant du fichier de langue (des grands
nombres, ex. 274368). Un chainon manque quelque part, jamais trouve malgre
plusieurs pistes (StringHashToValue.txt -- une table de reglages du jeu,
sans rapport). Les objets sont donc identifies par leur ID numerique et leur
`MODEL_NAME`, nettoye en un intitule lisible -- pas leur vrai nom.

CATEGORIES GARDEES

Sur 4452 lignes, seules celles dont `CODE_FACTORY_NAME` ressemble a un objet
qu'on PORTE ou qu'on VOIT sont retenues : equipement, armes et leurs skins,
skins de vehicule. Le reste -- recettes de craft, coffres, octrois de
monnaie -- n'a pas d'apparence a montrer.

    InfantryEquipment, InfantryCosmetic, EquippableContainer,
    Weapon, VehicleSkinShaderParameterGroupId

SORTIE

    navigateur_cosmetiques/
        icones/           chaque icone, en .png
        catalogue.json     un objet par ligne retenue
"""
import glob
import json
import os
import re
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from pack2 import Pack2, crc64                                   # noqa: E402
from dds2png import dds2png                                      # noqa: E402
from noms_locale import charger as charger_noms, nom_de          # noqa: E402

JEU = r"C:\Games\ROTK"
SORTIE = os.path.dirname(os.path.abspath(__file__))
ICONES = os.path.join(SORTIE, 'icones')

CATEGORIES_GARDEES = {
    'InfantryEquipment', 'InfantryCosmetic', 'EquippableContainer',
    'Weapon', 'VehicleSkinShaderParameterGroupId',
}

RARETE_LABEL = {'0': 'Banal', '5': 'Commun', '6': 'Peu commun',
               '7': 'Rare', '8': 'Tres rare'}
RARETE_COULEUR = {'0': '#9aa0a6', '5': '#4caf50', '6': '#4a90d9',
                  '7': '#a55eea', '8': '#e8b923'}


def index_archives():
    """Table hash -> (chemin archive, entree), une seule passe."""
    table = {}
    packs = {}
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


def parse_datasheet(brut):
    """#*COL1^COL2^...  puis des lignes val1^val2^...^ -- vire l'entete."""
    lignes = brut.decode('utf-8', 'replace').splitlines()
    entete = [c for c in lignes[0].lstrip('#*').split('^') if c]
    idx = {c: i for i, c in enumerate(entete)}
    lignes_val = [l.split('^') for l in lignes[1:] if l.strip()]
    return idx, lignes_val


def libelle_depuis_modele(nom_modele, code_factory, id_):
    """Un intitule lisible a partir du nom de modele, faute de vrai nom.

    'Weapons_AK47Skull_3P.adr' -> 'AK47 Skull' ; les suffixes techniques
    (_3P, _LOD0, .adr, .dme) sont retires, les majuscules internes eclatees
    en mots. Mieux qu'un ID nu, mais ce n'est PAS le nom du jeu.
    """
    if not nom_modele:
        return '%s #%s' % (code_factory, id_)
    s = re.sub(r'\.(adr|dme)$', '', nom_modele, flags=re.I)
    s = re.sub(r'^(Weapons?|SurvivorMale|SurvivorFemale|Common_Props)_', '', s)
    s = re.sub(r'_(3P|OnGround|LOD\d|Reflex)$', '', s, flags=re.I)
    s = re.sub(r'([a-z0-9])([A-Z])', r'\1 \2', s)
    s = s.replace('_', ' ').strip()
    return s or ('%s #%s' % (code_factory, id_))


# Le maillage INTERNE et le nom qu'affiche l'ICONE divergent parfois --
# releve sur trois cas confirmes en jeu cette session : le fichier s'appelle
# Weapons_M16A4_LOD0.dme mais son icone est Icon_Weapons_AR15_....dds ; le
# fusil a pompe live est PumpShotgun01 mais son icone dit RiotShotgun ; le
# sniper live est M24 mais son icone dit M40Sniper. Sans cette table, la
# correspondance par mot-cle rate ces trois familles entierement.
ALIAS_FAMILLE = {
    'ar15': 'm16a4',
    'm40sniper': 'm24',
    'riotshotgun': 'pumpshotgun01',
    'magnum': 'pistol_44magnum01',
    'm9': 'm9auto',
    'ak47': 'ak47classic',
}


def cle_famille(nom):
    """Le meme mot-cle, qu'on parte d'un nom de fichier .dme/.glb ou d'une
    icone Icon_....dds -- pour que les deux se recoupent.

    Etendu aux vetements en plus des armes : l'icone d'un vetement porte le
    prefixe 'Wear_SurvivorMale_<emplacement>_' (Chest, Legs, Head...) que le
    maillage ne repete pas de la meme facon -- les deux doivent perdre cet
    emplacement pour se recouper. Exception : les masques, dont le maillage
    s'appelle 'SurvivorMale_Head_Mask_UncleSam' -- 'Mask' fait partie du nom,
    pas de l'emplacement, sinon deux masques differents convergeraient vers
    la meme cle 'unclesam'/'pig' perdue dans le bruit.
    """
    s = re.sub(r'\.(dds|dme|glb|adr)$', '', nom, flags=re.I)
    s = re.sub(r'^Icon_', '', s, flags=re.I)
    s = re.sub(r'^(Weapons?_|Wear_SurvivorMale_|Common_Props_)', '', s, flags=re.I)
    if not re.match(r'^Head_Mask_', s, flags=re.I):
        s = re.sub(r'^SurvivorMale_', '', s, flags=re.I)
        s = re.sub(r'^(Head|Chest|Legs|Hands|Feet|Face|Back|Armor)_', '', s, flags=re.I)
    else:
        s = re.sub(r'^SurvivorMale_Head_Mask_', '', s, flags=re.I)
    s = re.sub(r'(_3P|_LOD\d|_OnGround|_Reflex|_Tintable)+$', '', s, flags=re.I)
    s = re.sub(r'_\d+$', '', s)  # identifiant numerique final d'une icone
    s = s.lower()
    return ALIAS_FAMILLE.get(s, s)


def relie_modeles_3d(retenus, sortie):
    """Deux passes, la directe puis la famille -- voir le README pour le
    detail de ce que chacune couvre et pourquoi l'autre ne suffit pas."""
    import csv as _csv
    dossier_glb = os.path.join(sortie, 'modeles3d')
    if not os.path.isdir(dossier_glb):
        return

    # Passe 1 : lien DIRECT, l'objet a son propre MODEL_NAME resolu.
    liste_3d = os.path.join(sortie, 'brut3d', 'liste.csv')
    direct = 0
    if os.path.exists(liste_3d):
        with open(liste_3d, encoding='utf-8') as f:
            mesh_par_adr = {l['adr']: l['mesh'] for l in _csv.DictReader(f)}
        for o in retenus:
            m = mesh_par_adr.get(o['modele'])
            if not m:
                continue
            glb = os.path.join(dossier_glb, os.path.splitext(m)[0] + '.glb')
            if os.path.exists(glb):
                o['modele3d'] = 'modeles3d/' + os.path.splitext(m)[0] + '.glb'
                o['modele3d_type'] = 'direct'
                direct += 1
    print('%d objets relies a leur propre modele 3D' % direct)

    # Passe 2 : FAMILLE, par mot-cle d'icone -- l'objet n'a pas son propre
    # maillage, mais son icone est celle (ou une variante numerotee) d'une
    # arme de base deja convertie. L'apparence exacte du reskin peut differer
    # -- c'est la forme et la famille qui sont sures, pas la texture precise.
    # Plusieurs fichiers reduisent parfois a la MEME famille -- Weapons_M16A4
    # et Weapons_AR15_Reflex donnent tous deux "m16a4" une fois l'alias
    # applique. Trie par longueur de nom croissante : la variante la plus
    # nue (sans lunette, sans crosse alternative...) gagne, plutot que
    # l'ordre arbitraire du systeme de fichiers.
    glb_par_famille = {}
    for nom in sorted(os.listdir(dossier_glb), key=len):
        if not nom.endswith('.glb'):
            continue
        k = cle_famille(nom)
        glb_par_famille.setdefault(k, nom)

    # Le nom du .adr qui a produit chaque glb de la bibliotheque -- pour que
    # le bouton d'extraction ait quelque chose a demander, meme sur un objet
    # sans MODEL_NAME propre. Plusieurs .adr peuvent viser le meme maillage
    # (Weapons_AK47.adr et Weapons_AK47Classic.adr donnent tous deux
    # Weapons_AK47Classic_LOD0.dme) -- n'importe lequel des deux marche pour
    # l'extraction, elle lit le maillage et les textures qu'IL declare.
    adr_par_mesh = {}
    dossier_gear = os.path.join(os.path.dirname(sortie), 'blender', 'gear')
    for cat in ('arme', 'casque', 'haut', 'bas', 'gants', 'kevlar'):
        chemin = os.path.join(dossier_gear, cat, 'index.csv')
        if not os.path.exists(chemin):
            continue
        with open(chemin, encoding='utf-8') as f:
            for l in _csv.DictReader(f):
                adr_par_mesh.setdefault(l['mesh'], l['adr'])

    famille = 0
    for o in retenus:
        if o.get('modele3d'):
            continue
        k = cle_famille(o['icone'])
        glb = glb_par_famille.get(k)
        if glb:
            o['modele3d'] = 'modeles3d/' + glb
            o['modele3d_type'] = 'famille'
            mesh = os.path.splitext(glb)[0] + '.dme'
            adr = adr_par_mesh.get(mesh)
            if adr:
                o['adr_famille'] = adr
            famille += 1
    print('%d objets relies par famille (icone -> arme de base)' % famille)

    # Passe 3 : le .adr DEDUIT DU NOM DE L'ICONE -- pour l'extraction seule.
    #
    # La passe 2 ne relie qu'aux pieces deja converties en .glb (la
    # bibliotheque 3D). Or les vetements et sacs nomment leur piece dans
    # leur icone :
    #     Icon_Wear_SurvivorMale_Back_Backpack_Military_237.dds
    #       -> SurvivorMale_Back_Backpack_Military.adr
    # Le suffixe numerique final identifie la VARIANTE (la couleur), pas une
    # piece differente. Quand ce .adr existe vraiment dans les archives, le
    # bouton d'extraction a de quoi travailler -- 434 objets de plus, sans
    # apercu 3D pour autant.
    def adr_depuis_icone(icone):
        s2 = re.sub(r'\.dds$', '', icone, flags=re.I)
        s2 = re.sub(r'^Icon_', '', s2, flags=re.I)
        s2 = re.sub(r'_\d+$', '', s2)
        base = re.sub(r'^Wear_', '', s2, flags=re.I)
        candidats = [base + '.adr']
        if base.startswith('SurvivorMale_'):
            candidats.append(base.replace('SurvivorMale_', 'SurvivorFemale_', 1) + '.adr')
        candidats.append(re.sub(r'_(Tintable|Basic|Plain)$', '', base) + '.adr')
        for c in candidats:
            if table.get(crc64(c)) is not None:
                return c
        return None

    deduits = 0
    for o in retenus:
        if o.get('modele') or o.get('adr_famille'):
            continue
        a = adr_depuis_icone(o['icone'])
        if a:
            o['adr_famille'] = a
            deduits += 1
    print('%d objets extractibles via le .adr deduit de leur icone' % deduits)


def main():
    print('indexation des archives...')
    table, packs = index_archives()
    print('  %d archives, %d entrees' % (len(packs), len(table)))

    idx_i, items = parse_datasheet(lire(table, packs, 'ClientItemDefinitions.txt'))
    idx_m, mappings = parse_datasheet(lire(table, packs, 'ImageSetMappings.txt'))
    idx_img, images = parse_datasheet(lire(table, packs, 'Images.txt'))

    # IMAGE_SET_ID -> nom de fichier .dds, un representant par set (les
    # variantes de type -- 4,5,6,7 -- pointent en pratique vers la meme image).
    fichier_par_image_id = {f[idx_img['ID']]: f[idx_img['FILE_NAME']]
                            for f in images if len(f) > idx_img['FILE_NAME']}
    icone_par_set = {}
    for f in mappings:
        if len(f) <= idx_m['IMAGE_ID']:
            continue
        set_id = f[idx_m['IMAGE_SET_ID']]
        if set_id in icone_par_set:
            continue
        icone_par_set[set_id] = fichier_par_image_id.get(f[idx_m['IMAGE_ID']])

    # Les VRAIS noms du jeu (voir tools/noms_locale.py) -- le lien
    # NAME_ID -> fichier de langue, longtemps introuvable, est resolu.
    noms_jeu = charger_noms(JEU)
    print('%d noms lus dans les fichiers de langue' % len(noms_jeu))
    sans_nom = 0

    retenus = []
    for f in items:
        if len(f) <= max(idx_i['CODE_FACTORY_NAME'], idx_i['IMAGE_SET_ID']):
            continue
        code = f[idx_i['CODE_FACTORY_NAME']]
        if code not in CATEGORIES_GARDEES:
            continue
        set_id = f[idx_i['IMAGE_SET_ID']]
        icone = icone_par_set.get(set_id)
        if not icone:
            continue
        rarete = f[idx_i['RARITY']] if len(f) > idx_i['RARITY'] else '0'
        modele = f[idx_i['MODEL_NAME']] if len(f) > idx_i['MODEL_NAME'] else ''
        derive = libelle_depuis_modele(modele, code, f[idx_i['ID']])
        name_id = f[idx_i['NAME_ID']] if len(f) > idx_i['NAME_ID'] else ''
        vrai = nom_de(noms_jeu, name_id)
        if not vrai:
            sans_nom += 1
        retenus.append({
            'id': f[idx_i['ID']],
            'categorie': code,
            'modele': modele,
            'libelle': vrai or derive,
            'libelle_modele': derive,
            'rarete': rarete,
            'rarete_label': RARETE_LABEL.get(rarete, rarete),
            'rarete_couleur': RARETE_COULEUR.get(rarete, '#888'),
            'icone': icone,
        })

    print('%d objets retenus (categories cosmetiques), dont %d sans nom de jeu'
          % (len(retenus), sans_nom))

    a_extraire = sorted({o['icone'] for o in retenus})
    print('%d icones distinctes a extraire' % len(a_extraire))

    os.makedirs(ICONES, exist_ok=True)
    manquantes = 0
    for i, nom_dds in enumerate(a_extraire, 1):
        cible = os.path.join(ICONES, os.path.splitext(nom_dds)[0] + '.png')
        if os.path.exists(cible):
            continue
        brut = lire(table, packs, nom_dds)
        if brut is None:
            manquantes += 1
            continue
        tmp = tempfile.NamedTemporaryFile(suffix='.dds', delete=False)
        tmp.write(brut)
        tmp.close()
        try:
            dds2png(tmp.name, cible)
        except Exception as e:
            manquantes += 1
            print('  echec %s : %s' % (nom_dds, e))
        finally:
            os.unlink(tmp.name)
        if i % 200 == 0:
            print('  %d / %d' % (i, len(a_extraire)))

    for o in retenus:
        o['icone_png'] = 'icones/' + os.path.splitext(o['icone'])[0] + '.png'

    # Modele 3D : les .glb sont produits par extraire_3d.py + convertir_3d.py
    # (lien direct) et convertir_familles.py (bibliotheque d'armes de base) --
    # pas ici, ce script-ci ne s'occupe que des icones. On relie juste ce qui
    # existe deja, pour ne pas le perdre a chaque regeneration du catalogue.
    relie_modeles_3d(retenus, SORTIE)

    for p in packs.values():
        p.close()

    with open(os.path.join(SORTIE, 'catalogue.json'), 'w', encoding='utf-8') as f:
        json.dump(retenus, f, ensure_ascii=False, indent=1)

    print('\n%d icones manquantes' % manquantes)
    print('-> %s' % os.path.join(SORTIE, 'catalogue.json'))
    print('-> %d fichiers dans %s' % (len(os.listdir(ICONES)), ICONES))


if __name__ == '__main__':
    main()
