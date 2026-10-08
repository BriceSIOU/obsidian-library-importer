# 📚 Obsidian Library Importer

Quand un livre (`.pdf` / `.epub`) arrive dans `~/Downloads` ou `~/Documents`, un service **systemd** ouvre un terminal **kitty** qui pose quelques questions (catégorie, couverture, lu ?, note…). Le service crée ensuite la fiche du livre dans un vault **Obsidian**, avec la couverture tirée d'OpenLibrary ou de Wikipédia, et l'affiche dans une galerie **Dataview** classée par catégorie.

Sans IA, sans clé d'API, uniquement avec la bibliothèque standard de Python.

| Dossier | Contenu |
|---|---|
| `importer/` | `library_importer.py` (modes `scan`, `add FICHIER`, `init`) |
| `systemd/` | Unités `--user` : `.path` (surveillance) et `.service` (scan) |
| `obsidian/` | Vue `Library_view.md` + snippet CSS galerie |
| `docs/` | Documentation complète avec diagrammes d'architecture (Mermaid) |

## Installation

```bash
sudo apt install poppler-utils libnotify-bin
./install.sh            # vault par défaut : ~/NOTES/Prime  (sinon VAULT=/chemin ./install.sh)
```

## Mise à jour du dépôt

```bash
./sync.sh "message"     # recopie la version installée, puis commit + push
```

Documentation : [docs/](docs/)
