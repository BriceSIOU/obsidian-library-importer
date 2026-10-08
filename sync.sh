#!/usr/bin/env bash
# Copie la version installée (live) dans le dépôt, puis commit + push.
# Usage : ./sync.sh "message de commit"
set -euo pipefail
R="$(cd "$(dirname "$0")" && pwd)"
V="$HOME/NOTES/Prime"

cp "$HOME/.local/share/library-importer/library_importer.py" "$R/importer/"
cp "$HOME/.config/systemd/user/library-importer.path" \
   "$HOME/.config/systemd/user/library-importer.service" "$R/systemd/"
cp "$V/.obsidian/snippets/library.css" "$R/obsidian/snippets/"
cp "$V/02 - Education/Library_view.md" "$R/obsidian/"
cp "$V/05 - Persistants Notes/Bibliothèque - Service d'import automatique.md" "$R/docs/"

cd "$R"
git add -A
if git diff --cached --quiet; then
  echo "Rien à synchroniser."
  exit 0
fi
git commit -m "${1:-Mise à jour}"
git push
