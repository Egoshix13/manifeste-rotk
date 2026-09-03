"""Fenetre autonome pour le manifeste -- pas un onglet de navigateur.

    python navigateur_cosmetiques/lanceur.py
    (ou, une fois compile : ManifesteROTK.exe)

POURQUOI UNE FENETRE A PART ET PAS "OUVRIR DANS LE NAVIGATEUR"

Un lien qu'on double-clique ouvre un onglet parmi vingt autres, sans icone
propre dans la barre des taches, facile a perdre. Une fenetre dediee se
distingue, se retrouve, se ferme comme un outil normal -- c'est le seul
changement que ce fichier apporte : `index.html` lui-meme est identique a
celui qu'on ouvrirait dans un navigateur.

CE QUI TIENT LA FENETRE

`pywebview` : pas un navigateur embarque a part entiere, une fine couche
Python par-dessus le moteur DEJA installe sur la machine -- Edge WebView2
sous Windows, present par defaut depuis Windows 10 (c'est le meme moteur
que Edge, donc le rendu est identique a ce qui a ete verifie dans le
navigateur). Ca evite d'embarquer un Chromium complet dans l'executable.

LES DONNEES RESTENT A COTE, PAS DANS L'EXECUTABLE

`index.html` et `icones/` restent des fichiers ordinaires a cote du .exe,
pas embarques dedans. Deux raisons :

  - 58 Mo d'icones dans l'executable en ferait un fichier enorme, et il
    faudrait le reconstruire et le redistribuer entierement pour la moindre
    mise a jour du catalogue ;
  - la ou ils sont, `extraire.py` peut les regenerer sur place sans jamais
    toucher a l'executable -- l'equipe recoit un nouveau dossier de donnees,
    pas un nouveau programme.

LE PONT VERS PYTHON

Le bouton "Extraire les fichiers" du panneau detail appelle
`window.pywebview.api.extraire_objet(...)` cote JS -- une fonction JS ne
peut pas ecrire sur le disque ni lire les archives du jeu, seul Python le
peut. `js_api=Api()` est ce pont : chaque methode de la classe devient
appelable depuis la page, et son retour (un dict JSON-compatible) revient
tel quel en JS. Voir extraction_a_la_demande.py pour ce que fait
l'extraction elle-meme.
"""
import base64
import binascii
import os
import sys
import tempfile
import threading
import time

import webview

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extraction_a_la_demande import (extraire, jeu_installe,        # noqa: E402
                                     precharger_index,
                                     definir_racine_perso, ressemble_au_jeu)

ICI = os.path.dirname(os.path.abspath(sys.argv[0] if getattr(sys, 'frozen', False)
                                      else __file__))
PAGE = os.path.join(ICI, 'index.html')
EXTRACTIONS = os.path.join(ICI, 'extractions')
CAPTURES = os.path.join(ICI, 'captures')
# Dossier du jeu choisi dans l'interface (engrenage) -- un simple fichier
# texte a cote de l'executable, pour survivre d'un lancement a l'autre.
CONFIG_CHEMIN = os.path.join(ICI, 'chemin_jeu.txt')


def _lire_chemin_memorise():
    try:
        with open(CONFIG_CHEMIN, encoding='utf-8') as f:
            return f.read().strip() or None
    except OSError:
        return None


def _precharger_en_fond():
    if jeu_installe():
        threading.Thread(target=precharger_index, daemon=True).start()


class Api:
    def jeu_disponible(self):
        return {'jeu': jeu_installe()}

    def chemin_jeu(self):
        return {'effectif': jeu_installe(),
                'personnalise': _lire_chemin_memorise()}

    def definir_chemin_jeu(self, chemin):
        chemin = (chemin or '').strip().strip('"')
        if not chemin:
            try:
                os.remove(CONFIG_CHEMIN)
            except OSError:
                pass
            definir_racine_perso(None)
            _precharger_en_fond()
            eff = jeu_installe()
            msg = ('Retour aux emplacements par defaut -- jeu trouve : %s' % eff
                   if eff else
                   'Retour aux emplacements par defaut -- jeu introuvable, '
                   'l\'extraction restera indisponible.')
            return {'ok': True, 'message': msg, 'effectif': eff}
        if not os.path.isdir(chemin):
            return {'ok': False, 'effectif': jeu_installe(),
                    'message': 'Dossier introuvable : %s' % chemin}
        if not ressemble_au_jeu(chemin):
            return {'ok': False, 'effectif': jeu_installe(),
                    'message': 'Aucune archive .pack2 dans %s -- ce n\'est '
                               'pas le dossier du jeu (attendu : celui qui '
                               'contient Resources\\Assets).' % chemin}
        try:
            with open(CONFIG_CHEMIN, 'w', encoding='utf-8') as f:
                f.write(chemin + '\n')
        except OSError as e:
            return {'ok': False, 'effectif': jeu_installe(),
                    'message': 'Impossible d\'enregistrer le choix : %s' % e}
        definir_racine_perso(chemin)
        _precharger_en_fond()
        return {'ok': True, 'effectif': jeu_installe(),
                'message': 'Dossier du jeu enregistre : %s' % chemin}

    # ---- cabine d'essayage : appliquer sa propre texture sur l'apercu 3D --
    # Un PNG se lit entierement en JS ; ces methodes servent a ce que le JS
    # ne sait pas faire : ouvrir une vraie boite de dialogue avec un CHEMIN
    # (pour pouvoir resurveiller le fichier ensuite), convertir un .dds, et
    # detecter qu'un export GIMP a ecrase le fichier (mode "suivre").

    def choisir_texture(self):
        choix = webview.windows[0].create_file_dialog(
            webview.OPEN_DIALOG, allow_multiple=False,
            file_types=('Textures (*.png;*.jpg;*.jpeg;*.dds)',
                        'Tous les fichiers (*.*)'))
        return {'chemin': choix[0] if choix else None}

    def mtime_texture(self, chemin):
        try:
            return {'mtime': os.path.getmtime(chemin)}
        except OSError:
            return {'mtime': None}

    def charger_texture(self, chemin):
        """Renvoie le fichier en data-URL, converti en PNG si c'est un .dds.

        Une texture 1024x1024 fait ~1-3 Mo -- la faire transiter en base64
        par le pont reste instantane en local, et evite toute question de
        droits d'acces du navigateur au disque."""
        try:
            mtime = os.path.getmtime(chemin)
        except OSError:
            return {'ok': False, 'message': 'Fichier introuvable : %s' % chemin}
        ext = os.path.splitext(chemin)[1].lower()
        if ext == '.dds':
            tmp = os.path.join(tempfile.gettempdir(),
                               'essayage_%d.png' % os.getpid())
            try:
                from dds2png import dds2png
                dds2png(chemin, tmp)
                with open(tmp, 'rb') as f:
                    data = f.read()
            except Exception as e:
                return {'ok': False,
                        'message': 'Conversion .dds impossible (%s). NVIDIA '
                                   'Texture Tools est-il installe ? Sinon, '
                                   'exportez la texture en .png.' % e}
            finally:
                try:
                    os.remove(tmp)
                except OSError:
                    pass
            mime = 'image/png'
        elif ext in ('.png', '.jpg', '.jpeg'):
            with open(chemin, 'rb') as f:
                data = f.read()
            mime = 'image/png' if ext == '.png' else 'image/jpeg'
        else:
            return {'ok': False, 'message': 'Format non gere : %s (attendu '
                                            '.png, .jpg ou .dds)' % ext}
        return {'ok': True, 'mtime': mtime,
                'data': 'data:%s;base64,%s' % (mime,
                                               base64.b64encode(data).decode())}

    def enregistrer_capture(self, libelle, data_url):
        """Ecrit le PNG du rendu 3D (envoye en data-URL par la page) dans
        captures/ a cote de l'executable. L'horodatage dans le nom permet
        d'enchainer les captures d'un meme objet sans rien ecraser."""
        try:
            donnees = base64.b64decode(data_url.split(',', 1)[1])
        except (IndexError, ValueError, binascii.Error):
            return {'ok': False, 'message': 'Donnees d\'image invalides.'}
        try:
            os.makedirs(CAPTURES, exist_ok=True)
            fichier = os.path.join(
                CAPTURES,
                '%s_%s.png' % (_nom_dossier(libelle),
                               time.strftime('%Y%m%d_%H%M%S')))
            with open(fichier, 'wb') as f:
                f.write(donnees)
        except OSError as e:
            return {'ok': False, 'message': 'Enregistrement impossible : %s' % e}
        return {'ok': True, 'chemin': fichier,
                'message': 'Capture enregistree : %s' % os.path.basename(fichier)}

    def ouvrir_captures(self):
        os.makedirs(CAPTURES, exist_ok=True)
        try:
            os.startfile(CAPTURES)
        except OSError:
            pass
        return {'ok': True}

    def extraire_objet(self, nom_adr, libelle):
        dossier = os.path.join(EXTRACTIONS, _nom_dossier(libelle))
        ok, message, fichiers = extraire(nom_adr, dossier)
        if ok:
            try:
                os.startfile(dossier)  # ouvre l'explorateur dessus
            except OSError:
                pass
        return {'ok': ok, 'message': message, 'dossier': dossier if ok else None}


def _nom_dossier(libelle):
    s = ''.join(c if c.isalnum() or c in ' -_' else '' for c in libelle)
    return s.strip().replace(' ', '_') or 'objet'


def main():
    if not os.path.exists(PAGE):
        webview.create_window(
            'Manifeste ROTK -- fichier manquant',
            html='<body style="font-family:sans-serif;padding:40px;'
                 'background:#16181A;color:#E8E6E0">'
                 '<h2>index.html introuvable</h2>'
                 '<p>Attendu a cote de ce programme :<br><code>%s</code></p>'
                 '<p>Le dossier <b>navigateur_cosmetiques</b> complet '
                 '(index.html + icones/) doit rester a cote de l\'executable.</p>'
                 '</body>' % PAGE,
            width=640, height=320)
        webview.start()
        return

    # Le chemin choisi via l'engrenage, s'il existe, prime sur les
    # emplacements par defaut.
    definir_racine_perso(_lire_chemin_memorise())

    # Parcourir tous les .pack2 du jeu prend plusieurs secondes -- le faire
    # maintenant, en fond, pour que le premier clic sur "Extraire" soit
    # immediat au lieu de paraitre gele. Sans le jeu installe, ne rien faire.
    _precharger_en_fond()

    webview.create_window(
        'Manifeste ROTK',
        PAGE,
        width=1280, height=860,
        min_size=(760, 520),
        background_color='#16181A',
        js_api=Api(),
    )
    webview.start()


if __name__ == '__main__':
    main()
