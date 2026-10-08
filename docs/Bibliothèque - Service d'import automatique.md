---
tags:
  - documentation
  - obsidian
  - systemd
  - bibliotheque
updated: 2026-10-08
---
# 📚 Bibliothèque : service d'import automatique

> [!info] En une phrase
> Quand un PDF ou un EPUB arrive dans `~/Downloads` ou `~/Documents`, systemd lance un script Python qui ouvre un terminal **kitty**. Le script te pose quelques questions, puis crée la fiche du livre dans Obsidian (avec couverture) et copie le fichier dans le vault. La note [[Library_view]] affiche ensuite tous les livres en galerie, rangés par catégorie.

> [!important] Tenir ce document à jour
> Toute modification du service (script, unités systemd, vue, CSS, dossiers surveillés) doit être reportée ici, y compris dans les diagrammes et dans le **Journal des modifications** en bas de page.

---

## 1. Vue d'ensemble

```mermaid
flowchart LR
    subgraph Navigateur["🌐 Téléchargement"]
        DL["Fichier .pdf / .epub"]
    end

    subgraph FS["📁 Dossiers surveillés"]
        D1["~/Downloads"]
        D2["~/Documents"]
    end

    subgraph SD["⚙️ systemd --user"]
        P["library-importer.path<br/>(surveillance inotify)"]
        S["library-importer.service<br/>(oneshot : scan)"]
        R["systemd-run<br/>(unité transitoire)"]
    end

    subgraph PY["🐍 library_importer.py"]
        SCAN["scan"]
        ADD["add FICHIER<br/>(questionnaire)"]
        ST[("state.json")]
    end

    subgraph EXT["☁️ APIs web"]
        OL["OpenLibrary<br/>search + covers"]
        WP["Wikipédia<br/>photo de l'auteur"]
    end

    subgraph OBS["🟣 Vault Obsidian « Prime »"]
        LIB["02 - Education/Library/*.md<br/>(fiches livres)"]
        AS["99 - Assets/<br/>(PDF + covers/)"]
        VIEW["Library_view.md<br/>(Dataview + CSS)"]
    end

    DL --> D1 & D2
    D1 & D2 -- "PathChanged" --> P
    P -- "déclenche" --> S
    S -- "exécute" --> SCAN
    SCAN <--> ST
    SCAN -- "doublon ?" --> AS
    SCAN -- "notify-send" --> N["🔔 Notification"]
    SCAN -- "nouveau livre" --> R
    R -- "ouvre" --> K["🖥️ kitty"]
    K --> ADD
    ADD -- "pdfinfo / pdftoppm" --> AS
    ADD -- "HTTP" --> OL & WP
    ADD -- "écrit" --> LIB
    ADD -- "copie / déplace" --> AS
    ADD -- "nouvelle catégorie" --> VIEW
    ADD -- "xdg-open obsidian://" --> O["Obsidian"]
    ADD --> N
    LIB --> VIEW
```

---

## 2. Déroulement d'un téléchargement

```mermaid
sequenceDiagram
    autonumber
    actor U as Toi
    participant FS as ~/Downloads
    participant P as library-importer.path
    participant S as library-importer.service
    participant SC as script (scan)
    participant K as kitty (via systemd-run)
    participant A as script (add)
    participant API as OpenLibrary / Wikipédia
    participant V as Vault Obsidian

    U->>FS: télécharge livre.pdf
    FS-->>P: événement inotify (fichier créé/renommé)
    P->>S: démarre le service
    S->>SC: python3 library_importer.py scan
    SC->>SC: déjà vu ? (state.json : chemin + date de modif)
    SC->>SC: attend que la taille soit stable (2 s)
    SC->>V: même contenu (SHA-256) déjà dans 99 - Assets ?
    alt doublon
        SC-->>U: 🔔 « … est déjà dans ta bibliothèque »
    else nouveau
        SC->>K: systemd-run kitty -- library_importer.py add livre.pdf
        K->>A: lance le questionnaire
        A->>U: Est-ce un livre ? Titre ? Auteur ?
        A->>API: recherche OpenLibrary
        API-->>A: 5 résultats (id, année, couverture)
        A->>U: Lequel ? Année ? Catégorie ? Couverture ? Lu ? Note ? Copier ?
        opt pas de couverture
            A->>API: photo de l'auteur (Wikipédia)
            Note over A: sinon pdftoppm : 1re page du PDF
        end
        A->>V: copie le PDF dans 99 - Assets
        A->>V: écrit la fiche dans Library/
        A->>V: ajoute une section si nouvelle catégorie
        A-->>U: 🔔 « … ajouté (catégorie) »
        A->>V: xdg-open obsidian://open?… (si demandé)
    end
```

---

## 3. Arbre de décision du `scan`

```mermaid
flowchart TD
    A["Fichier dans ~/Downloads ou ~/Documents<br/>(pas les sous-dossiers)"] --> B{"Extension<br/>.pdf ou .epub ?"}
    B -- non --> X1["Ignoré"]
    B -- oui --> C{"Dans state.json avec<br/>la même date de modif ?"}
    C -- oui --> X2["Ignoré (déjà traité)"]
    C -- non --> D["Attendre la fin du téléchargement<br/>(taille stable)"]
    D --> E{"Même contenu SHA-256<br/>qu'un fichier de 99 - Assets ?"}
    E -- oui --> F["status = duplicate<br/>🔔 notification"]
    E -- non --> G["status = pending<br/>ouvre kitty → questionnaire"]
    G --> H{"Est-ce un livre ?"}
    H -- non --> I["status = ignored"]
    H -- oui --> J["Fiche + PDF + couverture<br/>status = added"]
    G -. "Ctrl+C" .-> K["status = skipped"]
```

---

## 4. Composants : applications et programmes utilisés

### 4.1 Système (Pop!_OS 24.04, session GNOME)

| Composant | Paquet / emplacement | Rôle dans le service |
|---|---|---|
| **systemd (mode utilisateur)** | `systemd` | Surveille les dossiers (`.path`) et lance le script (`.service`). Démarre avec la session, sans droits root. |
| **systemd-run** | `systemd` | Lance kitty dans sa propre unité transitoire. Sans lui, systemd tuerait le terminal à la fin du service `oneshot`. |
| **kitty** | `~/.local/bin/kitty` | Terminal dans lequel s'affiche le questionnaire. |
| **Python 3.12** | `/usr/bin/python3` | Exécute le script. Uniquement la bibliothèque standard (`json`, `hashlib`, `urllib`, `fcntl`, `shutil`, `subprocess`, `pathlib`, `re`), rien à installer. |
| **pdfinfo** | `poppler-utils` | Lit le titre, l'auteur et le nombre de pages d'un PDF. |
| **pdftoppm** | `poppler-utils` | Transforme la 1re page du PDF en image JPEG (couverture de secours). |
| **notify-send** | `libnotify-bin` (0.8.3) | Notifications de bureau (« ajouté », « déjà dans ta bibliothèque »). |
| **xdg-open** | `xdg-utils` | Ouvre la fiche dans Obsidian via l'URI `obsidian://open?vault=Prime&file=…`. |

### 4.2 Services web

| Service | URL appelée | Rôle |
|---|---|---|
| **OpenLibrary Search** | `https://openlibrary.org/search.json?q=…` | Retrouve le livre : id de l'œuvre, année, auteurs, id de couverture. |
| **OpenLibrary Covers** | `https://covers.openlibrary.org/b/id/<id>-L.jpg` | Image de couverture (lien direct, rien n'est téléchargé). |
| **Wikipédia REST** | `https://{fr,en}.wikipedia.org/api/rest_v1/page/summary/<Auteur>` | Photo de l'auteur quand il n'y a pas de couverture. |

> [!note] Gratuit et sans clé
> Ces trois APIs sont gratuites et ne demandent ni compte ni clé. Le script s'identifie avec l'en-tête `User-Agent: library-importer/1.0`.

### 4.3 Obsidian

| Composant | Rôle |
|---|---|
| **Vault « Prime »** (`~/NOTES/Prime`) | Contient les fiches, les PDF et la vue. |
| **Plugin Dataview** | Construit les tableaux de [[Library_view]] à partir des propriétés des fiches. |
| **Plugin Media DB** | A défini le format des fiches (`type: book`, `dataSource: OpenLibraryAPI`…). Le script reproduit ce format. Le plugin peut toujours servir à ajouter un livre à la main. |
| **Snippet CSS `library`** | Transforme les tableaux Dataview en galerie de cartes, en pleine largeur. |
| **Thème ITS** | Thème actif. Le snippet force certains styles (`!important`) pour passer par-dessus. |

---

## 5. Fichiers

```mermaid
flowchart TD
    subgraph HOME["~ (home)"]
        subgraph CFG[".config/systemd/user/"]
            F1["library-importer.path"]
            F2["library-importer.service"]
        end
        subgraph SH[".local/share/library-importer/"]
            F3["library_importer.py"]
            F4["state.json"]
        end
        subgraph V["NOTES/Prime/ (vault)"]
            F5["02 - Education/Library_view.md"]
            F6["02 - Education/Library/*.md"]
            F7["99 - Assets/*.pdf"]
            F8["99 - Assets/covers/*.jpg"]
            F9[".obsidian/snippets/library.css"]
            F10[".obsidian/appearance.json"]
        end
    end
    F1 -->|déclenche| F2 -->|exécute| F3
    F3 <-->|lit / écrit| F4
    F3 -->|crée| F6 & F7 & F8
    F3 -->|ajoute une section| F5
    F5 -->|lit| F6
    F10 -->|active| F9 -->|style| F5
```

| Fichier | Contenu |
|---|---|
| `~/.config/systemd/user/library-importer.path` | `PathChanged=%h/Downloads` et `PathChanged=%h/Documents`, activé par `default.target`. |
| `~/.config/systemd/user/library-importer.service` | `Type=oneshot`, lance `python3 …/library_importer.py scan`. |
| `~/.local/share/library-importer/library_importer.py` | Le script (modes `scan`, `add`, `init`). |
| `~/.local/share/library-importer/state.json` | Mémoire des fichiers déjà traités. |
| `02 - Education/Library/<Titre> (<année>).md` | Une fiche par livre. |
| `02 - Education/Library_view.md` | La galerie : une section et un tableau Dataview par catégorie. |
| `99 - Assets/<Titre>.pdf` | Copie du livre. |
| `99 - Assets/covers/<slug>.jpg` | Couvertures extraites de la 1re page d'un PDF. |
| `.obsidian/snippets/library.css` | Style galerie, appliqué uniquement aux notes avec `cssclasses: library`. |

---

## 6. Détails de fonctionnement

### 6.1 `state.json` : ce que le script retient

```json
"~/Downloads/livre.pdf": { "status": "added", "mtime": 1791455757.31 }
```

| Statut | Signification |
|---|---|
| `existing` | Déjà présent lors de l'installation (`init`), jamais proposé. |
| `pending` | Fenêtre ouverte, ou fermée sans répondre. |
| `added` | Ajouté à la bibliothèque. |
| `ignored` | Tu as répondu « non, ce n'est pas un livre ». |
| `skipped` | Annulé avec Ctrl+C. |
| `duplicate` | Contenu identique à un livre déjà présent. |

Un fichier est considéré comme **déjà vu** seulement si son chemin **et** sa date de modification (`mtime`) correspondent. Un fichier supprimé puis retéléchargé sous le même nom a une nouvelle date : il est donc reproposé.

### 6.2 Détection des doublons
- On compare l'empreinte **SHA-256** du fichier avec celle des `.pdf`/`.epub` de `99 - Assets`.
- Seuls les fichiers **de même taille** sont hachés, ce qui rend la vérification quasi instantanée.
- La détection ne marche que si les fichiers sont identiques à l'octet près : une autre édition ou un autre scan n'est pas reconnu.

### 6.3 Choix de la couverture (dans l'ordre)
1. La couverture OpenLibrary, si le résultat choisi en a une (🖼 dans la liste).
2. Sinon, au choix :
   - **la photo de l'auteur** depuis Wikipédia (fr puis en). C'est la règle : pas de couverture → photo de l'auteur ;
   - **la 1re page du PDF** (`pdftoppm -r 60`), utilisée aussi si Wikipédia ne trouve rien ;
   - aucune image.

### 6.4 Format d'une fiche

```yaml
---
type: book
title: "Ultralearning"
englishTitle: "Ultralearning"
year: 2019
dataSource: OpenLibraryAPI
url: "https://openlibrary.org/works/OL20846121W"
id: "/works/OL20846121W"
author:
  - "Scott H. Young"
category: "Développement personnel"
pages: 241
image: "https://covers.openlibrary.org/b/id/10156205-L.jpg"   # ou "99 - Assets/covers/x.jpg"
read: false
personalRating: 0
tags: mediaDB/book
# + plot, isbn, isbn13, onlineRating, released, lastRead, subType (format Media DB)
---
[[Ultralearning.pdf]]

Note perso facultative…
```

### 6.5 La vue [[Library_view]]
- Une section `##` par catégorie : 💻 Informatique, 🔭 Science, 📚 Littérature, 🌱 Développement personnel. Une nouvelle catégorie créée par le script ajoute sa propre section à la fin.
- Chaque section contient la même requête Dataview :
  ```
  FROM "02 - Education/Library"
  WHERE type = "book" AND category = "<Catégorie>"
  SORT read ASC, year DESC
  ```
- **Couvertures** : une URL `http…` s'affiche avec `![|80](url)`. Une image locale doit passer par `embed(link(image))`, car Dataview n'affiche pas `![](chemin local)`.
- **Colonnes** : Couverture, Titre, Auteur, Année, Lu (✅/📖), Note (`x/10`).

---

## 7. Utilisation

```bash
# Relancer le questionnaire sur un fichier (après une erreur, ou un fichier hors des dossiers surveillés)
python3 ~/.local/share/library-importer/library_importer.py add ~/chemin/livre.pdf

# Marquer tous les fichiers actuels comme déjà vus (sans rien proposer)
python3 ~/.local/share/library-importer/library_importer.py init

# Couper / réactiver la surveillance
systemctl --user disable --now library-importer.path
systemctl --user enable  --now library-importer.path

# Voir l'état et l'historique
systemctl --user status library-importer.path
journalctl --user -u library-importer.service -n 20
```

**Marquer un livre comme lu** : dans la fiche, mettre `read: true` et `personalRating: 8`.

---

## 8. Dépannage

| Problème | Cause | Solution |
|---|---|---|
| Aucune fenêtre après un téléchargement | Fichier dans un sous-dossier, ou surveillance coupée | `systemctl --user status library-importer.path`, ou lancer `add` à la main |
| Fenêtre fermée par erreur | Le fichier reste `pending` | Lancer `add` à la main, ou supprimer et retélécharger le fichier |
| Pas de fenêtre, seulement une notification | Le fichier est un doublon exact | Normal. Lancer `add` à la main pour forcer l'ajout |
| Une couverture ne s'affiche pas | Image locale écrite en `![](…)` | La vue doit utiliser `embed(link(image))` |
| La vue n'est pas en galerie | Snippet désactivé | Paramètres → Apparence → Extraits CSS → `library` |
| Catégorie en double dans la liste | Guillemets lus avec la valeur (bug corrigé le 2026-10-08) | Vérifier `existing_categories()` |

> [!warning] Limites connues
> - Les sous-dossiers ne sont pas surveillés, exprès : les projets de dev (uploads…) déclencheraient des fenêtres.
> - Un document perso enregistré dans `~/Documents` (rapport, TP) ouvre aussi la fenêtre : réponds « non ».
> - Le nom du vault (`Prime`) et le chemin de kitty sont écrits en dur dans le script.

---

## 9. Journal des modifications

| Date | Changement |
|---|---|
| 2026-10-08 | Nettoyage des fiches existantes (TLPI, LDD), vue Dataview avec colonnes Année / Lu / Note |
| 2026-10-08 | Snippet CSS `library` : galerie de cartes pleine largeur |
| 2026-10-08 | Champ `category` et 4 sections. Import de 11 livres depuis `~/Documents` et `~/Downloads`, et de 3 depuis `~/Hack_android` |
| 2026-10-08 | Couvertures locales via `embed(link(image))` ; règle « pas de couverture → photo de l'auteur » |
| 2026-10-08 | Création du service : `library-importer.path` / `.service` + `library_importer.py` |
| 2026-10-08 | Copie par défaut (au lieu de déplacer) |
| 2026-10-08 | `state.json` avec `mtime` : un fichier retéléchargé sous le même nom est reproposé |
| 2026-10-08 | Détection des doublons par SHA-256 + notification |
| 2026-10-08 | Correctif : catégories en double (guillemets) dans le questionnaire |
| 2026-10-08 | Création de ce document |
