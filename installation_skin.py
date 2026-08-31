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


def archive_verrouillee(archive):
    """Le client de CETTE installation tourne-t-il ? Sonde le verrou sur
    l'archive elle-meme plutot que de chercher H1Z1.exe dans tasklist :
    deux clients peuvent coexister (C:\\Games\\ROTK + copie Steam) et un
    H1Z1.exe de l'AUTRE installation ne verrouille pas nos archives --
    refuser sur le seul nom du processus bloquerait a tort."""
    try:
        with open(archive, 'r+b'):
            return False
    except PermissionError:
        return True
    except OSError:
        # Autre erreur (archive disparue...) : laisser les etapes suivantes
        # la remonter avec un message plus precis.
        return False


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

    table, tout, packs = extraction._index()
    cibles = []
    for nom in noms:
        v = table.get(crc64(nom))
        if v is None:
            continue
        # la copie EFFECTIVE (celle que le jeu lit : derniere dans l'ordre
        # de chargement) decrit le format ; toutes les copies seront
        # remplacees a l'installation.
        archive, entree = v
        copies = tout.get(crc64(nom), [])
        donnees = packs[archive].read(entree)
        entete = _entete_dds(donnees) or {}
        cibles.append({
            'nom': nom,
            'archive': os.path.basename(archive),
            'copies': len(copies),
            'octets': len(donnees),
            'largeur': entete.get('largeur'),
            'hauteur': entete.get('hauteur'),
            'fourcc': entete.get('fourcc'),
            'origine_sauvee': _origine_existante(nom, copies),
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

def _fichier_origine(nom_cible, archive=None):
    """Sauvegarde d'origine d'UNE copie : le meme nom peut exister dans
    plusieurs archives avec des contenus differents, chaque copie a donc
    sa propre sauvegarde (suffixee par l'archive). Sans archive : l'ancien
    format a fichier unique, garde pour les sauvegardes deja faites."""
    if archive is None:
        return os.path.join(SAUVE_TEXTURES, nom_cible + '.original')
    return os.path.join(SAUVE_TEXTURES, '%s@%s.original'
                        % (nom_cible, os.path.basename(archive)))


def _origine_existante(nom_cible, copies):
    if os.path.exists(_fichier_origine(nom_cible)):
        return True
    return any(os.path.exists(_fichier_origine(nom_cible, a))
               for a, _ in copies)


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


def _sauvegarde_texture(nom_cible, archive, donnees, etapes):
    os.makedirs(SAUVE_TEXTURES, exist_ok=True)
    dst = _fichier_origine(nom_cible, archive)
    if os.path.exists(dst):
        etapes.append('origine de la copie %s deja sauvegardee, conservee'
                      % os.path.basename(archive))
        return
    with open(dst, 'wb') as f:
        f.write(donnees)
    etapes.append('origine de la copie %s sauvegardee (%d octets)'
                  % (os.path.basename(archive), len(donnees)))


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
        # Dimensions differentes : AVERTIR, pas refuser. Agrandir l'atlas
        # est une technique legitime et eprouvee -- le casque Oakley est un
        # 2048 pose sur un original 512, confirme en jeu.
        if (entete_origine and
                (entete['largeur'], entete['hauteur']) !=
                (entete_origine['largeur'], entete_origine['hauteur'])):
            etapes.append('dimensions %dx%d (original %dx%d) -- atlas '
                          'redimensionne, voulu ?'
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
            etapes.append('PNG %dx%d (original %dx%d) -- atlas redimensionne, '
                          'voulu ?' % (dims[0], dims[1],
                                       entete_origine['largeur'],
                                       entete_origine['hauteur']))
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
    """Verifications communes a installer() et restaurer(). Retourne
    (erreur, plan) ou plan = [(archive, donnees_actuelles), ...] pour
    CHAQUE copie du nom -- le jeu lit la derniere, mais un meme nom peut
    exister en plusieurs versions et toutes doivent etre traitees."""
    if extraction.jeu_installe() is None:
        return 'Jeu introuvable sur cette machine.', None
    _table, tout, packs = extraction._index()
    copies = tout.get(crc64(nom_cible))
    if not copies:
        return '%s introuvable dans les archives.' % nom_cible, None
    for archive in {a for a, _ in copies}:
        if archive_verrouillee(archive):
            return ('%s est verrouillee -- le client de cette installation '
                    'tourne, fermez-le. Rien n\'a ete modifie.'
                    % os.path.basename(archive)), None
    return None, [(a, packs[a].read(e)) for a, e in copies]


def _fermer_archives_indexees():
    """pack2_patch rouvre les archives en ecriture ; les descripteurs
    LECTURE de l'index ne l'empechent pas sous Windows, mais leurs
    positions de table deviennent fausses apres relogement. On invalide
    l'index : il se reconstruira a la prochaine operation."""
    with extraction._VERROU_INDEX:
        if extraction._INDEX is not None:
            for p in extraction._INDEX[2].values():
                try:
                    p.close()
                except OSError:
                    pass
        extraction._INDEX = None


def installer(nom_cible, fichier):
    """Remplace TOUTES les copies de `nom_cible` dans les archives du jeu
    par `fichier`. Le jeu lit la derniere copie, mais laisser trainer les
    autres versions rendrait l'etat incoherent (et la 'premiere' copie est
    parfois un dechet perime d'un vieux patch)."""
    etapes = []
    erreur, plan = _prealables(nom_cible)
    if erreur:
        return {'ok': False, 'message': erreur, 'etapes': etapes}

    # Le format de reference est celui de la copie EFFECTIVE (la derniere,
    # celle que le jeu lit) -- dans sa version d'origine si on l'a deja
    # remplacee une fois.
    archive_eff, donnees_eff = plan[-1]
    origine_eff = _fichier_origine(nom_cible, archive_eff)
    if os.path.exists(origine_eff):
        with open(origine_eff, 'rb') as f:
            entete_origine = _entete_dds(f.read(128))
    else:
        entete_origine = _entete_dds(donnees_eff)
    a_ecrire, temporaire, erreur = _preparer_dds(fichier, entete_origine, etapes)
    if erreur:
        return {'ok': False, 'message': erreur, 'etapes': etapes}

    try:
        for archive, donnees in plan:
            if not _sauvegarde_archive(archive, etapes):
                return {'ok': False, 'message': 'Sauvegarde d\'archive non '
                                                'verifiee, on s\'arrete la.',
                        'etapes': etapes}
            _sauvegarde_texture(nom_cible, archive, donnees, etapes)

        _fermer_archives_indexees()
        for archive, _donnees in plan:
            patch(archive, nom_cible, a_ecrire, verbose=False)
            if not verifie(archive, nom_cible, a_ecrire):
                return {'ok': False, 'etapes': etapes,
                        'message': 'La relecture dans %s ne correspond pas a '
                                   'ce qui a ete ecrit -- restaurez.'
                                   % os.path.basename(archive)}
        etapes.append('ecrit et relu identique dans %d copie(s) : %s'
                      % (len(plan), ', '.join(os.path.basename(a)
                                              for a, _ in plan)))
    except PermissionError:
        return {'ok': False, 'message': 'Archive verrouillee (jeu ou launcher '
                                        'ouvert ?).', 'etapes': etapes}
    except OSError as e:
        return {'ok': False, 'message': 'Erreur disque : %s' % e, 'etapes': etapes}
    finally:
        if temporaire:
            try:
                os.remove(a_ecrire)
            except (OSError, TypeError):
                pass
        _fermer_archives_indexees()

    return {'ok': True, 'etapes': etapes,
            'message': '%s installee (%d copie(s)). Le skin est en place -- le '
                       'launcher peut le defaire a une mise a jour, reinstaller '
                       'suffira.' % (nom_cible, len(plan))}


def restaurer(nom_cible):
    """Remet chaque copie a sa version d'origine sauvegardee."""
    etapes = []
    erreur, plan = _prealables(nom_cible)
    if erreur:
        return {'ok': False, 'message': erreur, 'etapes': etapes}

    travaux = []
    for archive, _donnees in plan:
        origine = _fichier_origine(nom_cible, archive)
        if not os.path.exists(origine) and len(plan) == 1:
            origine = _fichier_origine(nom_cible)  # ancien format, mono-copie
        if os.path.exists(origine):
            travaux.append((archive, origine))
    if not travaux:
        return {'ok': False, 'etapes': etapes,
                'message': 'Aucune texture d\'origine sauvegardee pour %s -- '
                           'rien a restaurer.' % nom_cible}
    try:
        _fermer_archives_indexees()
        for archive, origine in travaux:
            patch(archive, nom_cible, origine, verbose=False)
            if not verifie(archive, nom_cible, origine):
                return {'ok': False, 'etapes': etapes,
                        'message': 'La relecture dans %s ne correspond pas a '
                                   'l\'origine.' % os.path.basename(archive)}
            etapes.append('origine reecrite dans %s' % os.path.basename(archive))
    except PermissionError:
        return {'ok': False, 'message': 'Archive verrouillee (jeu ou launcher '
                                        'ouvert ?).', 'etapes': etapes}
    except OSError as e:
        return {'ok': False, 'message': 'Erreur disque : %s' % e, 'etapes': etapes}
    finally:
        _fermer_archives_indexees()
    return {'ok': True, 'etapes': etapes,
            'message': '%s restauree a l\'original (%d copie(s)).'
                       % (nom_cible, len(travaux))}
