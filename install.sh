#!/usr/bin/env bash
# Installe le service d'import de livres sur une nouvelle machine.
# Prérequis : python3, poppler-utils (pdfinfo, pdftoppm), libnotify-bin, kitty, Obsidian + Dataview.
set -euo pipefail
R="$(cd "$(dirname "$0")" && pwd)"
V="${VAULT:-$HOME/NOTES/Prime}"

install -Dm755 "$R/importer/library_importer.py" "$HOME/.local/share/library-importer/library_importer.py"
install -Dm644 "$R/systemd/library-importer.path"    "$HOME/.config/systemd/user/library-importer.path"
install -Dm644 "$R/systemd/library-importer.service" "$HOME/.config/systemd/user/library-importer.service"
install -Dm644 "$R/obsidian/snippets/library.css"    "$V/.obsidian/snippets/library.css"
mkdir -p "$V/02 - Education/Library" "$V/99 - Assets/covers"
# ne jamais écraser une vue existante
[ -e "$V/02 - Education/Library_view.md" ] || cp "$R/obsidian/Library_view.md" "$V/02 - Education/"

# marque les fichiers déjà présents comme vus, puis active la surveillance
python3 "$HOME/.local/share/library-importer/library_importer.py" init
systemctl --user daemon-reload
systemctl --user enable --now library-importer.path

echo "✅ Installé. Active le snippet « library » dans Obsidian : Paramètres → Apparence → Extraits CSS."
