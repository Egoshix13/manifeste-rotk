# Manifeste ROTK — navigateur de cosmétiques

Catalogue local des objets du jeu (armes, équipement, sacs, skins de
véhicule) : icône, rareté, catégorie, recherche. Pour explorer ce qui existe
avant de choisir quoi personnaliser.

## Utilisation

Double-clic sur **`ManifesteROTK.exe`**. C'est tout — aucune installation,
pas besoin du jeu installé sur la machine, ça s'ouvre dans sa propre
fenêtre.

**Le dossier entier doit voyager ensemble** : l'exécutable, `index.html`,
`icones/`, `modeles3d/` et `polices/` sont liés. Envoyer seulement le `.exe`
ouvre une fenêtre qui dit poliment qu'il manque `index.html` — zippez tout
`navigateur_cosmetiques/`. Les polices sont embarquées dans `polices/`
(auparavant chargées depuis Google Fonts) : l'appli ne touche plus du tout
au réseau.

## Pourquoi une fenêtre à part

`ManifesteROTK.exe` n'est qu'un habillage : une fenêtre dédiée autour
d'`index.html`, via `pywebview` (le même moteur qu'Edge, déjà présent sur
Windows — rien n'est réembarqué). Sans lui, `index.html` s'ouvre tout aussi
bien dans un navigateur ordinaire ; l'exécutable sert juste à avoir un
programme qu'on retrouve, qu'on épingle, qu'on ferme comme un outil et pas
un onglet perdu parmi vingt autres.

## Ce qui manque, en connaissance de cause

Les objets sont identifiés par leur ID et le nom de leur modèle 3D, **pas**
leur nom affiché en jeu. Le lien entre l'identifiant de nom du jeu et la
table de traduction n'a pas été retrouvé — voir `extraire.py` pour le détail
de ce qui a été essayé. Un objet sans nom de modèle apparaît comme
`Categorie #id`.

## Mettre à jour le catalogue

Après une mise à jour du jeu, sur une machine qui a `C:\Games\ROTK`
installé :

    python extraire.py

Ça régénère `catalogue.json` et `icones/`. Renvoyer le dossier
`navigateur_cosmetiques/` complet à l'équipe — l'exécutable, lui, n'a pas
besoin d'être refait.

## Reconstruire l'exécutable

Seulement si `lanceur.py` change :

    pip install pywebview pyinstaller
    python -m PyInstaller --onefile --windowed --name ManifesteROTK ^
        --distpath navigateur_cosmetiques ^
        --workpath build --specpath build ^
        --paths tools ^
        --icon navigateur_cosmetiques/icone/ManifesteROTK.ico ^
        --version-file navigateur_cosmetiques/icone/version_info.txt ^
        navigateur_cosmetiques/lanceur.py

**`--paths tools` est indispensable** : l'extraction à la demande importe
`pack2` et `dds2png` depuis `tools/`, un dossier qui n'est PAS distribué
avec l'appli — ils doivent donc être embarqués dans l'exécutable. Sans ce
drapeau, l'exe compile sans erreur mais crashe au lancement avec
`ModuleNotFoundError: No module named 'pack2'`.

## Modèles 3D

901 objets (sur 1885) ont un aperçu 3D tournant à la place de la simple
icône — répartis en deux badges :

- **`3D`** (89 objets) : référence directe dans la table du jeu.
- **`3D~`** (812 objets) : pas de référence propre, mais l'icône identifie
  une pièce de base déjà modélisée — armes ET vêtements (casques, hauts,
  bas, gants, kevlar, sacs), toute la bibliothèque extraite depuis le début
  du projet. Forme et famille sûres, texture précise du reskin possiblement
  différente.

Restent hors d'atteinte : les skins de véhicule (paramètres de shader, pas
une texture) et une partie des vêtements et sacs sans icône reconnaissable.
Voir `extraire_3d.py` et `convertir_familles.py` pour le détail.

Affiché via [`<model-viewer>`](https://modelviewer.dev) (Google), la
bibliothèque est en local dans `model-viewer.min.js` — aucune connexion
requise pour l'utiliser une fois le dossier reçu.

### Régénérer les modèles 3D

Sur une machine avec `C:\Games\ROTK` installé :

    python extraire_3d.py
    blender --background --factory-startup --python convertir_3d.py

Le premier script extrait maillages et textures depuis le jeu
(`brut3d/`, pas nécessaire à distribuer) ; le second les convertit en
`.glb` avec matériau couleur intégré (`modeles3d/`, ce qui doit
accompagner l'app). Relancer ensuite `extraire.py` pour relier chaque
objet du catalogue à son `.glb`.

**Deux sortes d'aperçu 3D**, distinguées par le badge sur la fiche :

- **`3D`** (plein) : l'objet a sa propre référence de maillage dans la table
  du jeu — modèle et texture exacts.
- **`3D~`** (atténué) : pas de référence propre, mais son icône est celle
  d'une arme de base déjà modélisée (souvent partagée par plusieurs objets
  du même modèle). La forme et la famille sont sûres, la texture précise du
  reskin peut différer — le panneau détail le rappelle à chaque fois.

## Cabine d'essayage 3D

Sur tout objet avec aperçu 3D, le bouton **Essayer ma texture** applique un
fichier à soi (`.png`, `.jpg` ou `.dds`) sur le modèle qui tourne — sans
compresser, installer, ni lancer le jeu. Un `.png` peut aussi être glissé
directement sur l'aperçu. **Texture d'origine** revient à l'état normal.

La case **Suivre ce fichier** (dans `ManifesteROTK.exe` seulement)
surveille le fichier choisi : à chaque export depuis GIMP, l'aperçu se
recharge tout seul — on peint à gauche, le modèle tourne à droite.

Détails à savoir :

- La conversion `.dds` passe par NVIDIA Texture Tools ; sans lui, un
  message l'explique — exporter en `.png` marche toujours.
- Sur un objet `3D~` (modèle de famille), l'atlas UV peut différer
  légèrement du reskin exact — même réserve que l'aperçu lui-même.
- Dans un navigateur ordinaire, seul le glisser-déposer / choix d'un
  `.png` local fonctionne (pas de pont Python pour le `.dds` ni le suivi).

## Extraire les fichiers d'un objet

Le panneau détail porte un bouton qui sort maillage brut + *toutes* les
textures déclarées (couleur, normale, spéculaire — pas seulement la
couleur) dans un dossier ouvert automatiquement dans l'explorateur. Deux
cas, texte du bouton différent :

- **Modèle exact** (badge `3D`) : **Extraire les fichiers du jeu** — l'objet
  a sa propre référence, ce sont ses vrais fichiers.
- **Famille** (badge `3D~`) : **Extraire l'arme de base** — pas de
  référence propre, mais l'arme de base identifiée par l'icône. Le
  panneau le rappelle en toutes lettres avant le bouton : c'est un point
  de départ pour créer un skin, pas le reskin exact tel qu'il apparaît
  en jeu.

**Ne marche que sur une machine avec le jeu installé** — les archives
sources ne voyagent pas avec l'appli (plusieurs dizaines de Go). Le jeu est
cherché dans `C:\Games\ROTK` puis dans le dossier Steam habituel ;
**installé ailleurs, l'engrenage en haut de la fenêtre** permet de coller
son chemin (celui qui contient `Resources\Assets`). Le choix est vérifié
(présence d'archives `.pack2`), retenu dans un `chemin_jeu.txt` à côté de
l'exécutable, et un bouton « Par défaut » l'oublie. Dans un navigateur
ordinaire plutôt que `ManifesteROTK.exe`, le bouton d'extraction et
l'engrenage restent visibles mais désactivés, avec un message clair.

Les fichiers `.png` à côté des `.dds` ne se génèrent que si NVIDIA Texture
Tools est installé sur la machine — sinon les `.dds` brutes suffisent,
elles s'ouvrent directement dans Blender.

## Identité de l'appli

`ManifesteROTK.exe` porte maintenant sa propre icône et ses métadonnées
(éditeur, description, version) — visibles dans les Propriétés du fichier
sous Windows, au lieu d'apparaître comme un exécutable anonyme. Le logo
source est dans `icone/logo.svg`, à modifier là si l'équipe veut changer le
visuel — puis reconstruire l'`.ico` et recompiler (commande dans le
paragraphe précédent, avec en plus `--icon` et `--version-file` pointant
vers `icone/ManifesteROTK.ico` et `icone/version_info.txt`).

Windows peut quand même afficher un avertissement SmartScreen au premier
lancement — c'est le cas de tout exécutable non signé numériquement, quel
que soit le soin apporté au reste. Une vraie signature de code demande un
certificat payant, hors de portée d'un outil interne.

## Interface

- Logo (la couronne de `icone/logo.svg`) dans l'en-tête, aux couleurs du
  thème.
- Bascule clair / sombre dans l'en-tête — sans clic, le thème suit celui
  de Windows ; un clic fige le choix (retenu d'une session à l'autre).
- Puce **Aperçu 3D** pour ne montrer que les 901 objets qui en ont un, et
  menu **Tri** (ID, nom, rareté).
- Recherche insensible aux accents, raccourci `/` pour y sauter.
- La liste complète s'affiche par vagues au fil du défilement — plus de
  plafond silencieux à 600 fiches.
- Au clavier, le focus entre dans le panneau détail à l'ouverture et
  revient sur la fiche à la fermeture.
- Barre de filtres compactée sur deux lignes (recherche, puis toutes les
  puces catégorie/rareté ensemble) au lieu de trois.
- Un pouls discret sur les vignettes le temps que l'icône arrive du disque
  — 1622 fichiers, ça peut prendre un instant sur les premières cartes.
- Le panneau détail s'élargit automatiquement pour un objet avec aperçu 3D
  (680px contre 520px), pour avoir la place de le manipuler.

## Fenêtre console qui clignotait à l'extraction

Corrigé — la conversion `.dds` → `.png` passe par `nvdecompress.exe`, un
programme console. Sans précaution, Windows lui ouvre une fenêtre à chaque
appel, même quand on capture sa sortie : invisible en ligne de commande (une
console tourne déjà), visible depuis l'appli (compilée sans aucune console).
`tools/dds2png.py` lance maintenant ce sous-processus avec
`CREATE_NO_WINDOW`.
