"""Installation d'un skin dans les archives du jeu, depuis l'appli.

GENERALISE tools/pose_hoodie.py et pose_casque_oakley.py, les deux scripts
deja valides en jeu, en gardant leurs regles durement apprises :

  - ecriture SUR PLACE dans le .pack2 (pack2_patch), jamais de
    reconstruction d'archive ;
  - le jeu doit etre FERME (les .pack2 sont verrouilles sinon) ;
  - SAUVEGARDE AVANT TOUT : l'archive complete (une fois, verifiee
    SHA-256, jamais ecrasee -- elle date de l'archive intacte) ET la
    texture d'origine seule (pour le bouton Restaurer, cible) ;
  - RELECTURE apres ecriture : l'asset est relu depuis l'archive et
    compare octet a octet a ce qu'on a voulu ecrire ;
  - le launcher peut REPARER silencieusement une archive a la mise a
    jour : reinstaller est normal, l'operation est idempotente.

CE QUE CETTE V1 NE FAIT PAS, en connaissance de cause : les poses
"detournees" comme le hoodie (decalque d'un AUTRE objet + echange de
maillage dans Models.txt). Ici on remplace les textures DECLAREES par le
.adr de l'objet lui-meme -- le cas standard des reskins d'armes et
d'objets a reference propre.
"""
import hashlib
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(ICI), 'tools'))
sys.path.insert(0, os.path.join(ICI, 'tools'))
from pack2 import Pack2, crc64                                    # noqa: E402
from pack2_patch import patch, verifie, place_disponible          # noqa: E402
import extraction_a_la_demande as extraction                      # noqa: E402

# A cote de l'executable (meme logique que lanceur.py), pour que les
# sauvegardes voyagent avec l'appli et pas avec le depot de dev.
BASE = os.path.dirname(os.path.abspath(sys.argv[0] if getattr(sys, 'frozen', False)
                                       else __file__))
DOSSIER_SAUVEGARDES = os.path.join(BASE, 'sauvegardes')
SAUVE_ARCHIVES = os.path.join(DOSSIER_SAUVEGARDES, 'archives')
SAUVE_TEXTURES = os.path.join(DOSSIER_SAUVEGARDES, 'textures')

# Cartes de service partagees par tout le jeu -- les remplacer changerait
# des centaines d'objets, on ne les propose jamais comme cible.
_PLACEHOLDERS = ('white.dds', 'black.dds', 'grey.dds', 'detail_cube.dds')


# ---------------------------------------------------------------- lecture --

def _entete_dds(donnees):
    """Dimensions / format / mipmaps d'un blob DDS (en-tete de 128 octets)."""
    if len(donnees) < 128 or donnees[:4] != b'DDS ':
        return None
    _size, _flags, h, w, _pitch, _depth, mips = struct.unpack_from('<7I', donnees, 4)
    _pfflags, fourcc = struct.unpack_from('<I4s', donnees, 0x50)
    return {'largeur': w, 'hauteur': h, 'mips': mips,
            'fourcc': fourcc.decode('ascii', 'replace').strip('\x00')}


def _dimensions_png(chemin):
    """Largeur/hauteur d'un PNG, lues directement dans l'IHDR (pas de PIL)."""
    with open(chemin, 'rb') as f:
        d = f.read(24)
    if len(d) < 24 or d[:8] != b'\x89PNG\r\n\x1a\n':
        return None
    w, h = struct.unpack('>II', d[16:24])
    return w, h


def jeu_tourne():
    try:
        s = subprocess.run(['tasklist'], capture_output=True, text=True,
                           creationflags=subprocess.CREATE_NO_WINDOW
                           if os.name == 'nt' else 0).stdout
    except OSError:
        return False
    return 'H1Z1.exe' in s


def lister_cibles(nom_adr):
    """Les textures declarees par le .adr de l'objet, chacune avec son
    archive, son format et son etat (origine sauvegardee = deja modifiee
    au moins une fois par nous)."""
    if extraction.jeu_installe() is None:
        return {'ok': False, 'message': 'Jeu introuvable sur cette machine.'}
    d = extraction._lire(nom_adr)
    nom_reel = nom_adr
    if d is None:
        for v in extraction._variantes(nom_adr):
            d = extraction._lire(v)
            if d is not None:
                nom_reel = v
                break
    if d is None:
        return {'ok': False,
                'message': '%s introuvable dans les archives.' % nom_adr}

    noms = sorted(set(t.decode() for t in re.findall(rb'textureName="([^"]+)"', d)))
    noms = [t for t in noms if t.lower() not in _PLACEHOLDERS]

    table, packs = extraction._index()
    cibles = []
    for nom in noms:
        v = table.get(crc64(nom))
        if v is None:
            continue
        archive, entree = v
        donnees = packs[archive].read(entree)
        entete = _entete_dds(donnees) or {}
        cibles.append({
            'nom': nom,
            'archive': os.path.basename(archive),
            'octets': len(donnees),
            'largeur': entete.get('largeur'),
            'hauteur': entete.get('hauteur'),
            'fourcc': entete.get('fourcc'),
            'origine_sauvee': os.path.exists(_fichier_origine(nom)),
        })

    if not cibles:
        return {'ok': False,
                'message': '%s ne declare aucune texture remplacable.' % nom_reel}

    # La carte couleur d'abord : _C, sinon le decalque _DT, sinon la premiere.
    defaut = next((c['nom'] for c in cibles if c['nom'].lower().endswith('_c.dds')),
                  next((c['nom'] for c in cibles if '_dt' in c['nom'].lower()),
                       cibles[0]['nom']))
    # Le chemin de l'installation VISEE, affiche en toutes lettres : deux
    # installations identiques peuvent coexister (C:\Games\ROTK + copie
    # Steam) et patcher la mauvaise ne previent par aucune erreur -- une
    # session entiere y est passee sur le hoodie.
    return {'ok': True, 'cibles': cibles, 'defaut': defaut,
            'jeu': extraction.jeu_installe()}


# ----------------------------------------------------------- sauvegardes --

def _fichier_origine(nom_cible):
    return os.path.join(SAUVE_TEXTURES, nom_cible + '.original')


def _sha(chemin):
    h = hashlib.sha256()
    with open(chemin, 'rb') as f:
        for bloc in iter(lambda: f.read(1 << 22), b''):
            h.update(bloc)
    return h.hexdigest()


def _sauvegarde_archive(archive, etapes):
    """Copie complete de l'archive, une seule fois, verifiee SHA-256.
    Jamais ecrasee : une sauvegarde existante date de l'archive INTACTE."""
    os.makedirs(SAUVE_ARCHIVES, exist_ok=True)
    dst = os.path.join(SAUVE_ARCHIVES, os.path.basename(archive) + '.original')
    if os.path.exists(dst):
        etapes.append('sauvegarde d\'archive deja presente (%s), conservee'
                      % os.path.basename(dst))
        return True
    shutil.copy2(archive, dst)
    if _sha(archive) != _sha(dst):
        try:
            os.remove(dst)
        except OSError:
            pass
        etapes.append('ECHEC : la copie de sauvegarde ne correspond pas (SHA-256)')
        return False
    etapes.append('archive sauvegardee et verifiee SHA-256 (%s, %.0f Mo)'
                  % (os.path.basename(dst), os.path.getsize(dst) / 1048576))
    return True


def _sauvegarde_texture(nom_cible, donnees, etapes):
    os.makedirs(SAUVE_TEXTURES, exist_ok=True)
    dst = _fichier_origine(nom_cible)
    if os.path.exists(dst):
        etapes.append('texture d\'origine deja sauvegardee, conservee')
        return
    with open(dst, 'wb') as f:
        f.write(donnees)
    etapes.append('texture d\'origine sauvegardee (%d octets)' % len(donnees))


# ----------------------------------------------------------- installation --

def _preparer_dds(fichier, entete_origine, etapes):
    """Le fichier a ecrire, au format DDS. Un .dds est verifie contre
    l'original ; un .png est compresse au MEME format (BC1/BC3) et doit
    avoir les memes dimensions. Retourne (chemin, temporaire?, erreur)."""
    ext = os.path.splitext(fichier)[1].lower()

    if ext == '.dds':
        with open(fichier, 'rb') as f:
            entete = _entete_dds(f.read(128))
        if entete is None:
            return None, False, '%s : pas un fichier DDS valide.' % fichier
        if (entete_origine and
                (entete['largeur'], entete['hauteur']) !=
                (entete_origine['largeur'], entete_origine['hauteur'])):
            return None, False, (
                'Dimensions %dx%d, mais la texture du jeu fait %dx%d -- '
                'mauvais atlas, rien n\'a ete ecrit.'
                % (entete['largeur'], entete['hauteur'],
                   entete_origine['largeur'], entete_origine['hauteur']))
        if entete_origine and entete['fourcc'] != entete_origine['fourcc']:
            etapes.append('attention : format %s alors que l\'original est en %s'
                          % (entete['fourcc'] or '?', entete_origine['fourcc'] or '?'))
        return fichier, False, None

    if ext == '.png':
        dims = _dimensions_png(fichier)
        if dims is None:
            return None, False, '%s : pas un PNG valide.' % fichier
        if entete_origine and dims != (entete_origine['largeur'],
                                       entete_origine['hauteur']):
            return None, False, (
                'PNG %dx%d, mais la texture du jeu fait %dx%d -- mauvais '
                'atlas, rien n\'a ete ecrit.'
                % (dims[0], dims[1],
                   entete_origine['largeur'], entete_origine['hauteur']))
        try:
            from png2dds import png2dds, png2dds_bc3
        except ImportError:
            return None, False, ('Conversion PNG indisponible (outil manquant). '
                                 'Fournissez un .dds deja compresse.')
        tmp = os.path.join(tempfile.gettempdir(),
                           'installation_%d.dds' % os.getpid())
        fourcc = (entete_origine or {}).get('fourcc') or 'DXT1'
        try:
            if fourcc == 'DXT1':
                png2dds(fichier, tmp)
            elif fourcc in ('DXT5', 'DXT3'):
                png2dds_bc3(fichier, tmp)
            else:
                return None, False, ('Format d\'origine %s non gere pour la '
                                     'conversion -- fournissez un .dds.' % fourcc)
        except Exception as e:
            return None, False, ('Compression PNG -> DDS echouee (%s). NVIDIA '
                                 'Texture Tools est-il installe ?' % e)
        etapes.append('PNG compresse en %s (nvcompress)' % fourcc)
        return tmp, True, None

    return None, False, ('Format %s non gere pour l\'installation -- '
                         '.png ou .dds.' % (ext or 'sans extension'))


def _prealables(nom_cible):
    """Verifications communes a installer() et restaurer().
    Retourne (erreur, archive, donnees_actuelles)."""
    if extraction.jeu_installe() is None:
        return 'Jeu introuvable sur cette machine.', None, None
    if jeu_tourne():
        return ('H1Z1.exe tourne -- fermez le jeu (les archives sont '
                'verrouillees). Rien n\'a ete modifie.'), None, None
    table, packs = extraction._index()
    v = table.get(crc64(nom_cible))
    if v is None:
        return '%s introuvable dans les archives.' % nom_cible, None, None
    archive, entree = v
    return None, archive, packs[archive].read(entree)


def _fermer_archive_indexee(archive):
    """pack2_patch rouvre l'archive en ecriture ; le descripteur LECTURE que
    l'index garde ouvert n'empeche pas ca sous Windows, mais ses positions
    de table peuvent devenir fausses apres relogement. On invalide l'index :
    il se reconstruira a la prochaine operation."""
    with extraction._VERROU_INDEX:
        if extraction._INDEX is not None:
            for p in extraction._INDEX[1].values():
                try:
                    p.close()
                except OSError:
                    pass
        extraction._INDEX = None


def installer(nom_cible, fichier):
    """Remplace `nom_cible` dans les archives du jeu par `fichier`."""
    etapes = []
    erreur, archive, donnees = _prealables(nom_cible)
    if erreur:
        return {'ok': False, 'message': erreur, 'etapes': etapes}

    entete_origine = _entete_dds(donnees)
    a_ecrire, temporaire, erreur = _preparer_dds(fichier, entete_origine, etapes)
    if erreur:
        return {'ok': False, 'message': erreur, 'etapes': etapes}

    try:
        if not _sauvegarde_archive(archive, etapes):
            return {'ok': False, 'message': 'Sauvegarde d\'archive non verifiee, '
                                            'rien n\'a ete ecrit.', 'etapes': etapes}
        _sauvegarde_texture(nom_cible, donnees, etapes)

        _fermer_archive_indexee(archive)
        patch(archive, nom_cible, a_ecrire, verbose=False)
        if not verifie(archive, nom_cible, a_ecrire):
            return {'ok': False, 'message': 'La relecture ne correspond pas a ce '
                                            'qui a ete ecrit -- restaurez la '
                                            'sauvegarde.', 'etapes': etapes}
        etapes.append('ecrit dans %s puis relu : identique'
                      % os.path.basename(archive))
    except PermissionError:
        return {'ok': False, 'message': 'Archive verrouillee (jeu ou launcher '
                                        'ouvert ?). Rien n\'a ete modifie.',
                'etapes': etapes}
    except OSError as e:
        return {'ok': False, 'message': 'Erreur disque : %s' % e, 'etapes': etapes}
    finally:
        if temporaire:
            try:
                os.remove(a_ecrire)
            except (OSError, TypeError):
                pass
        _fermer_archive_indexee(archive)

    return {'ok': True, 'etapes': etapes,
            'message': '%s installee. Le skin est en place -- le launcher peut '
                       'le defaire a une mise a jour, reinstaller suffira.'
                       % nom_cible}


def restaurer(nom_cible):
    """Remet la texture d'origine sauvegardee lors de la premiere installation."""
    etapes = []
    origine = _fichier_origine(nom_cible)
    if not os.path.exists(origine):
        return {'ok': False, 'etapes': etapes,
                'message': 'Aucune texture d\'origine sauvegardee pour %s -- '
                           'rien a restaurer.' % nom_cible}
    erreur, archive, _ = _prealables(nom_cible)
    if erreur:
        return {'ok': False, 'message': erreur, 'etapes': etapes}
    try:
        _fermer_archive_indexee(archive)
        patch(archive, nom_cible, origine, verbose=False)
        if not verifie(archive, nom_cible, origine):
            return {'ok': False, 'message': 'La relecture ne correspond pas a '
                                            'l\'origine.', 'etapes': etapes}
    except PermissionError:
        return {'ok': False, 'message': 'Archive verrouillee (jeu ou launcher '
                                        'ouvert ?). Rien n\'a ete modifie.',
                'etapes': etapes}
    except OSError as e:
        return {'ok': False, 'message': 'Erreur disque : %s' % e, 'etapes': etapes}
    finally:
        _fermer_archive_indexee(archive)
    etapes.append('texture d\'origine reecrite dans %s' % os.path.basename(archive))
    return {'ok': True, 'etapes': etapes,
            'message': '%s restauree a l\'original.' % nom_cible}
