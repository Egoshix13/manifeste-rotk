# Manifeste ROTK

**Navigateur local des cosmétiques du jeu ROTK** — catalogue complet des
objets (armes, équipement, sacs, skins), aperçus 3D manipulables, et une
cabine d'essayage pour voir ses propres textures sur les modèles du jeu
sans rien installer ni lancer le jeu.

100 % local : aucune connexion réseau, aucune donnée collectée, aucun
compte. Un dossier, un double-clic, c'est tout.

## Fonctionnalités

### Catalogue
- **1885 objets** avec leur **vrai nom du jeu**, icône, rareté et
  catégorie — extraits des fichiers du jeu par les scripts de ce dépôt.
- **Recherche instantanée** (insensible aux accents, raccourci `/`),
  filtres par catégorie, rareté, favoris et présence d'un aperçu 3D,
  tri par ID, nom ou rareté.
- **Vue famille** : depuis n'importe quel objet, voir tous les reskins
  du même modèle de base (jusqu'à 69 sur l'AR-15) — ce qui existe déjà,
  avant de créer le sien.
- **Favoris** persistants pour se constituer une liste de travail.
- Thème clair / sombre (suit Windows, ou se fige d'un clic).

### Aperçus 3D
- **901 objets** ont un modèle 3D qui tourne (`model-viewer`, embarqué) :
  badge `3D` pour un modèle exact, `3D~` pour l'arme ou le vêtement de
  base de la même famille.

### Cabine d'essayage
- **Essayer sa propre texture** (`.png`, `.jpg`, `.dds`) sur le modèle
  3D — glisser-déposer ou boîte de dialogue, retour à l'origine en un
  clic, historique des 5 dernières textures.
- **Mode « suivre ce fichier »** : l'aperçu se recharge à chaque export
  depuis GIMP — on peint à gauche, le modèle tourne à droite.
- **Export en image** : un PNG du rendu sous l'angle affiché, pour
  partager un skin en cours sans capture d'écran ni lancement du jeu.

### Sur une machine où le jeu est installé
- **Extraction à la demande** : le maillage et toutes les textures d'un
  objet (couleur, normale, spéculaire) sortis des archives `.pack2` en un
  clic, dans un dossier ouvert automatiquement.
- Chemin du jeu configurable dans l'interface (engrenage) si le jeu
  n'est pas à l'emplacement habituel.

## Utilisation

Deux façons, au choix :

1. **Sans exécutable** — ouvrir `index.html` dans n'importe quel
   navigateur. Tout fonctionne sauf l'extraction et le suivi de fichier
   (qui demandent le pont Python).
2. **`ManifesteROTK.exe`** (onglet [Releases](../../releases)) — une
   fenêtre dédiée avec toutes les fonctionnalités. À poser dans le
   dossier complet du dépôt (il a besoin d'`index.html`, `icones/`,
   `modeles3d/`, `polices/`).

## D'où vient l'exécutable ?

L'exe n'est **pas** versionné dans ce dépôt : celui de chaque Release est
**compilé automatiquement par GitHub Actions** depuis les sources de ce
dépôt ([workflow](.github/workflows/compiler.yml), journal public dans
l'onglet *Actions*). N'importe qui peut aussi le reconstruire :

    pip install pywebview pyinstaller
    python -m PyInstaller --onefile --windowed --name ManifesteROTK ^
        --paths tools --icon icone/ManifesteROTK.ico ^
        --version-file icone/version_info.txt lanceur.py

**Vérifier qu'une Release sort bien du build GitHub** (et pas d'un
téléversement) — deux preuves indépendantes :

1. **SHA-256** : chaque Release affiche l'empreinte de l'exe, imprimée
   dans le journal de compilation (non modifiable, généré par GitHub).
   Recalculer localement et comparer :

       Get-FileHash ManifesteROTK.exe

2. **Attestation de provenance** (signée par GitHub via Sigstore) : lie
   cryptographiquement le fichier à ce dépôt, ce commit et ce workflow.

       gh attestation verify ManifesteROTK.exe --owner Egoshix13

> **Note antivirus** : comme tout exécutable PyInstaller non signé,
> certains moteurs le signalent à tort sur VirusTotal (le lanceur
> s'auto-décompresse en mémoire, un motif que les heuristiques associent
> aux malwares). Le code est entièrement lisible ici — `lanceur.py`
> n'ouvre aucune connexion réseau — et la provenance de chaque Release
> est vérifiable comme ci-dessus.

## Sous le capot

| Fichier | Rôle |
|---|---|
| `index.html` | Toute l'application (catalogue embarqué, aucune dépendance en ligne) |
| `lanceur.py` | La fenêtre pywebview et le pont JS ↔ Python |
| `extraction_a_la_demande.py` | Lecture des archives du jeu pour l'extraction |
| `extraire.py`, `extraire_3d.py`, `convertir_*.py` | Régénération du catalogue, des icônes et des modèles 3D après une mise à jour du jeu |
| `tools/` | Lecture `.pack2` et conversion `.dds` (copies embarquées) |

Documentation détaillée : [LISEZ-MOI.md](LISEZ-MOI.md).

## Limites connues

- Les skins de véhicule n'ont pas d'aperçu 3D (paramètres de shader, pas
  de texture).
- Un objet sur 1885 n'a pas de nom dans les fichiers de langue et garde
  son intitulé dérivé du modèle.
