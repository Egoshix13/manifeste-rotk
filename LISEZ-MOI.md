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

## Les vrais noms du jeu

Les objets portent désormais **leur nom affiché en jeu** (« AR-15 »,
« Fire Hazard AR-15 », « inboxes AR-15»…) : 1884 sur 1885. Le chaînon
manquant a été trouvé — le fichier de langue indexe ses textes par

    Jenkins lookup2("Global.Text.<NAME_ID>", initval 0)

Voir `tools/noms_locale.py`. L'intitulé dérivé du nom de modèle est
conservé dans `libelle_modele` : il reste affiché dans le panneau détail
et cherchable, pour retrouver un objet par son nom de fichier.

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
        --paths navigateur_cosmetiques/tools ^
        --icon navigateur_cosmetiques/icone/ManifesteROTK.ico ^
        --version-file navigateur_cosmetiques/icone/version_info.txt ^
        navigateur_cosmetiques/lanceur.py

**`--paths navigateur_cosmetiques/tools` est indispensable** : l'extraction
à la demande importe `pack2` et `dds2png` depuis cette copie embarquée
(voir `tools/LISEZ-MOI.md`) — ils doivent être compilés DANS l'exécutable.
Sans ce drapeau, l'exe compile sans erreur mais crashe au lancement avec
`ModuleNotFoundError: No module named 'pack2'`.

### Compilation automatique (GitHub Actions)

Le dépôt GitHub compile aussi l'exe tout seul : pousser un tag `v*`
(ex. `v1.3.0`) déclenche `.github/workflows/compiler.yml`, qui construit
`ManifesteROTK.exe` sur les serveurs de GitHub et l'attache à la Release
du tag. Intérêt : la provenance est vérifiable par n'importe qui — le
binaire sort exactement des sources visibles, journal de compilation à
l'appui (onglet *Actions*).

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

**Exporter en image** enregistre un PNG du rendu, sous l'angle affiché,
avec la texture du moment (la vôtre ou celle d'origine) — de quoi montrer
un skin en cours sans lancer le jeu ni faire de capture d'écran. Dans
l'exe, les fichiers s'accumulent dans `captures/` (horodatés, rien ne
s'écrase) ; dans un navigateur, c'est un téléchargement ordinaire.

Détails à savoir :

- La conversion `.dds` passe par NVIDIA Texture Tools ; sans lui, un
  message l'explique — exporter en `.png` marche toujours.
- Sur un objet `3D~` (modèle de famille), l'atlas UV peut différer
  légèrement du reskin exact — même réserve que l'aperçu lui-même.
- Dans un navigateur ordinaire, seul le glisser-déposer / choix d'un
  `.png` local fonctionne (pas de pont Python pour le `.dds` ni le suivi).

## Installer un skin dans le jeu

Sur un objet à référence propre (badge `3D` plein), le panneau détail porte
**Installer dans le jeu…** : il remplace une texture de l'objet directement
dans les archives `.pack2`, généralisant les scripts `pose_*.py` du dépôt
parent (mêmes règles, durement apprises) :

- **le jeu doit être fermé** (les archives sont verrouillées sinon) —
  vérifié avant toute écriture ;
- **sauvegardes systématiques** au premier passage, dans `sauvegardes/` à
  côté de l'exe : l'archive complète (vérifiée SHA-256, jamais écrasée) et
  la texture d'origine seule (pour **Restaurer l'original**) ;
- la cible se choisit parmi les textures que le `.adr` déclare (la carte
  couleur `_C` présélectionnée), avec dimensions et format affichés ;
- un `.png` est compressé au format exact de l'original (DXT1/DXT5, via
  NVIDIA Texture Tools) ; les mauvaises dimensions sont refusées AVANT
  d'écrire quoi que ce soit ;
- écriture **sur place** dans l'archive (jamais de reconstruction), puis
  relecture et comparaison octet à octet ;
- le launcher peut défaire l'installation à une mise à jour — réinstaller
  suffit, l'opération est idempotente.

Hors de portée, sciemment : les poses « détournées » comme le hoodie
(décalque d'un autre objet + échange de maillage dans `Models.txt`) —
c'est l'affaire des scripts dédiés `tools/pose_*.py` du dépôt parent.

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

### Pourquoi certains objets n'ont pas de bouton

Extraire suppose de savoir **quel `.adr`** décrit l'objet. Trois cas :

| | Objets | Bouton |
|---|---|---|
| Référence propre (`MODEL_NAME` renseigné) | 154 | **Extraire les fichiers du jeu** — les vrais fichiers |
| Pièce de base retrouvée (par la bibliothèque 3D, ou par le nom de l'icône) | 1215 | **Extraire la pièce de base** — la pièce nue, pas le reskin |
| Rien de trouvable | 516 | aucun bouton |

Les 516 sans bouton se répartissent ainsi :

- **87 skins de véhicule** : ils n'ont ni maillage ni texture à eux, ce
  sont des paramètres de shader. Rien à extraire, par nature.
- **~360 objets à icône générique** : `Icon_ClothStrip.dds`,
  `Icon_FannyPack.dds`… l'icône ne nomme aucune pièce, et la table du jeu
  ne donne pas de modèle. Comme pour les skins d'armes, cette
  correspondance vit **côté serveur** (table d'apparence envoyée à la
  connexion) — elle n'est pas dans les fichiers du client.
- **69 pièces portées** dont le `.adr` déduit du nom n'existe pas dans les
  archives (nom de fichier qui ne suit pas la convention).

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

Mise en page d'outil : **barre du haut** (logo, compteur, réglages, thème)
et **barre latérale collante** qui garde recherche, filtres et tri sous la
main pendant que la grille défile — au lieu d'une pile de puces qui
poussait la grille vers le bas.

- **Fiches** : liseré de rareté en haut, vignette sur fond dégradé, nom sur
  deux lignes, pied compact (ID, badge 3D, étoile favori, pastille rareté).
  Survol : élévation et ombre portée.
- **Filtres** groupés par bloc titré (Catégorie, Rareté, Sélection, Ordre),
  puces arrondies avec compteur ; les puces de rareté portent leur couleur.
- **Panneau détail** : en-tête collant, aperçu 3D sur une scène en dégradé
  radial, cabine d'essayage dans son propre encart, fiche technique en
  colonnes.
- **Thème clair / sombre** : palettes retravaillées (papier chaud / gris
  bleuté profond), le thème suit Windows sauf choix explicite.
- La liste complète s'affiche par vagues au fil du défilement — pas de
  plafond silencieux.
- Recherche insensible aux accents, raccourci `/` pour y sauter.
- Au clavier, le focus entre dans le panneau à l'ouverture et revient sur
  la fiche à la fermeture.

## Fenêtre console qui clignotait à l'extraction

Corrigé — la conversion `.dds` → `.png` passe par `nvdecompress.exe`, un
programme console. Sans précaution, Windows lui ouvre une fenêtre à chaque
appel, même quand on capture sa sortie : invisible en ligne de commande (une
console tourne déjà), visible depuis l'appli (compilée sans aucune console).
`tools/dds2png.py` lance maintenant ce sous-processus avec
`CREATE_NO_WINDOW`.
