#!/usr/bin/env python3
"""Ajoute les livres téléchargés à la bibliothèque Obsidian.

  library_importer.py scan        appelé par systemd : ouvre un terminal par nouveau PDF/EPUB
  library_importer.py add FICHIER  questionnaire interactif pour un fichier
  library_importer.py init        marque les fichiers déjà présents comme vus
"""
import fcntl
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

try:  # module local facultatif (non versionné), voir cmd_add
    import paper_importer as extension
except ImportError:
    extension = None

HOME = Path.home()
WATCHED = [HOME / "Downloads", HOME / "Documents"]
EXTS = {".pdf", ".epub"}
VAULT = HOME / "NOTES/Prime"
LIBRARY = VAULT / "02 - Education/Library"
VIEW = VAULT / "02 - Education/Library_view.md"
ASSETS = VAULT / "99 - Assets"
COVERS = ASSETS / "covers"
STATE = Path(__file__).with_name("state.json")
# systemd-run : sinon systemd tue le terminal quand le service "scan" se termine
TERMINAL = ["systemd-run", "--user", "--quiet", "--collect", "--",
            str(HOME / ".local/bin/kitty"), "--title", "📚 Bibliothèque", "--"]
CATEGORIES = ["Informatique", "Science", "Littérature", "Développement personnel"]
UA = {"User-Agent": "library-importer/1.0 (personal Obsidian script)"}


# ---------- état (quels fichiers ont déjà été traités) ----------

def update_state(path=None, status=None):
    STATE.touch()
    with open(STATE, "r+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        txt = f.read()
        state = json.loads(txt) if txt.strip() else {}
        if path is not None:
            # mtime : un fichier retéléchargé sous le même nom est reproposé
            p = Path(path)
            state[str(path)] = {"status": status,
                                "mtime": p.stat().st_mtime if p.exists() else None}
            f.seek(0)
            f.truncate()
            json.dump(state, f, indent=1, ensure_ascii=False)
        return state


def prune_state():
    """Oublie les fichiers qui n'existent plus (supprimés, déplacés dans le vault…)."""
    STATE.touch()
    with open(STATE, "r+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        txt = f.read()
        state = json.loads(txt) if txt.strip() else {}
        kept = {k: v for k, v in state.items() if Path(k).exists()}
        if len(kept) != len(state):
            f.seek(0)
            f.truncate()
            json.dump(kept, f, indent=1, ensure_ascii=False)


def already_seen(state, p):
    entry = state.get(str(p))
    if entry is None:
        return False
    if isinstance(entry, str):  # ancien format, sans mtime
        return True
    return entry.get("mtime") == p.stat().st_mtime


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def find_duplicate(p):
    """Renvoie le nom de la fiche si ce fichier (même contenu) est déjà dans 99 - Assets."""
    size = p.stat().st_size
    for a in ASSETS.rglob("*"):
        # on ne hache que les fichiers de même taille : rapide même avec beaucoup de livres
        if a.is_file() and a.suffix.lower() in EXTS and a.stat().st_size == size and sha256(a) == sha256(p):
            for note in LIBRARY.glob("*.md"):
                if f"[[{a.name}]]" in note.read_text():
                    return note.stem
            return a.name
    return None


def candidates():
    for d in WATCHED:
        for p in d.iterdir():
            if p.is_file() and p.suffix.lower() in EXTS and not p.name.startswith("."):
                yield p


def cmd_init():
    for p in candidates():
        if str(p) not in update_state():
            update_state(p, "existing")
    print(f"{len(update_state())} fichiers marqués comme déjà vus.")


def cmd_scan():
    prune_state()
    state = update_state()
    for p in candidates():
        if already_seen(state, p):
            continue
        # attendre que le téléchargement soit terminé (taille stable)
        size = -1
        while size != p.stat().st_size:
            size = p.stat().st_size
            time.sleep(2)
        dup = find_duplicate(p)
        if dup:
            update_state(p, "duplicate")
            subprocess.run(["notify-send", "📚 Bibliothèque", f"« {dup} » est déjà dans ta bibliothèque"])
            continue
        update_state(p, "pending")
        subprocess.Popen(TERMINAL + [sys.executable, __file__, "add", str(p)],
                         start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


# ---------- petites aides ----------

def ask(q, default=""):
    a = input(f"{q}{f' [{default}]' if default else ''} : ").strip()
    return a or default


def yes(q, default=False):
    a = input(f"{q} [{'O/n' if default else 'o/N'}] : ").strip().lower()
    return default if not a else a in ("o", "oui", "y", "yes")


def choose(q, options):
    for i, o in enumerate(options, 1):
        print(f"  {i}) {o}")
    while True:
        a = input(f"{q} : ").strip()
        if a.isdigit() and 1 <= int(a) <= len(options):
            return int(a) - 1
        print("  → tape un numéro de la liste")


def get_json(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.load(r)


def pdf_info(path):
    info = {}
    if path.suffix.lower() == ".pdf":
        out = subprocess.run(["pdfinfo", str(path)], capture_output=True, text=True).stdout
        for line in out.splitlines():
            k, _, v = line.partition(":")
            info[k.strip()] = v.strip()
    return info


def safe_name(s):
    return re.sub(r'[\\/:*?"<>|#^\[\]]', "", s).strip()


def slug(s):
    s = re.sub(r"[^\w]+", "-", s.lower(), flags=re.UNICODE)
    return s.strip("-")[:60]


def unique(path):
    n, out = 2, path
    while out.exists():
        out = path.with_name(f"{path.stem} ({n}){path.suffix}")
        n += 1
    return out


def author_photo(name):
    for lang in ("fr", "en"):
        try:
            d = get_json(f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/"
                         + urllib.parse.quote(name.replace(" ", "_")))
        except Exception:
            continue
        img = d.get("originalimage") or d.get("thumbnail")
        if img and d.get("type") != "disambiguation":
            return img["source"].split("?")[0]
    return ""


def first_page_cover(pdf, title):
    if pdf.suffix.lower() != ".pdf":
        return ""
    COVERS.mkdir(parents=True, exist_ok=True)
    out = unique(COVERS / f"{slug(title)}.jpg")
    subprocess.run(["pdftoppm", "-jpeg", "-r", "60", "-f", "1", "-l", "1", "-singlefile",
                    str(pdf), str(out.with_suffix(""))], check=True)
    return str(out.relative_to(VAULT))


def add_category_section(cat):
    """Ajoute une section dans Library_view.md en recopiant le bloc de la 1re catégorie."""
    text = VIEW.read_text()
    if f'category = "{cat}"' in text:
        return
    m = re.search(r"```dataview.*?```", text, re.S)
    block = re.sub(r'category = "[^"]*"', f'category = "{cat}"', m.group(0))
    VIEW.write_text(text.rstrip() + f"\n\n## {cat}\n\n{block}\n")


def existing_categories():
    cats = list(CATEGORIES)
    for f in LIBRARY.glob("*.md"):
        m = re.search(r"^category: (.+)$", f.read_text(), re.M)
        cat = m.group(1).strip().strip("\"'") if m else ""  # le script écrit category: "X"
        if cat and cat not in cats:
            cats.append(cat)
    return cats


# ---------- questionnaire ----------

def cmd_add(path):
    path = Path(path)
    info = pdf_info(path)
    print(f"\n📚 Nouveau document : {path.name}")
    if info.get("Pages"):
        print(f"   {info['Pages']} pages — titre PDF : {info.get('Title') or '?'} — auteur PDF : {info.get('Author') or '?'}")
    print()
    dup = find_duplicate(path)
    if dup and not yes(f"⚠️  Ce fichier est déjà dans ta bibliothèque (« {dup} »). L'ajouter quand même ?"):
        update_state(path, "duplicate")
        return
    # extension optionnelle : un module local peut prendre en charge d'autres types de documents
    if extension and extension.maybe_handle(path, info, sys.modules[__name__]):
        return
    if not yes("Est-ce un livre à ajouter à ta bibliothèque ?"):
        update_state(path, "ignored")
        print("OK, ignoré. Je ne te le redemanderai pas.")
        return

    title = ask("Titre", info.get("Title") or path.stem.replace("_", " ").replace("-", " "))
    author = ask("Auteur(s), séparés par ;", info.get("Author", ""))

    # OpenLibrary
    work, cover, year, english = "", "", "", title
    try:
        q = urllib.parse.quote(f"{title} {author}".strip())
        docs = get_json(f"https://openlibrary.org/search.json?q={q}&limit=5"
                        "&fields=key,title,author_name,first_publish_year,cover_i")["docs"]
    except Exception as e:
        print(f"  (OpenLibrary injoignable : {e})")
        docs = []
    if docs:
        print("\nRésultats OpenLibrary :")
        opts = [f"{d.get('title')} — {', '.join(d.get('author_name', []))} ({d.get('first_publish_year', '?')})"
                + (" 🖼" if d.get("cover_i") else "") for d in docs] + ["Aucun de ceux-là"]
        i = choose("Lequel est ton livre ?", opts)
        if i < len(docs):
            d = docs[i]
            work = d["key"].split("/")[-1]
            english = d.get("title", title)
            year = str(d.get("first_publish_year", ""))
            if not author:
                author = "; ".join(d.get("author_name", []))
            if d.get("cover_i"):
                cover = f"https://covers.openlibrary.org/b/id/{d['cover_i']}-L.jpg"
    year = ask("Année", year)
    authors = [a.strip() for a in author.split(";") if a.strip()] or ["unknown"]

    print("\nCatégorie :")
    cats = existing_categories()
    i = choose("Numéro", cats + ["Nouvelle catégorie…"])
    category = cats[i] if i < len(cats) else ask("Nom de la nouvelle catégorie")

    # couverture
    if cover and not yes("\nUtiliser la couverture OpenLibrary ?", True):
        cover = ""
    if not cover:
        print("\nPas de couverture :")
        i = choose("Image", ["Photo de l'auteur (Wikipédia)", "Première page du PDF", "Aucune image"])
        if i == 0:
            cover = author_photo(authors[0])
            print(f"  → {cover or 'aucune photo trouvée, je prends la première page'}")
            if not cover:
                i = 1
        if i == 1:
            cover = first_page_cover(path, title)

    read = yes("\nDéjà lu ?")
    rating = ask("Note sur 10 (vide = pas de note)", "") if read else ""
    note = ask("Une note perso (pourquoi ce livre, qui te l'a conseillé…) — optionnel", "")
    move = not yes("Copier le fichier dans le vault (non = le déplacer) ?", True)

    # PDF -> 99 - Assets
    dest = unique(ASSETS / f"{safe_name(title)}{path.suffix.lower()}")
    (shutil.move if move else shutil.copy2)(path, dest)

    # fiche
    fname = unique(LIBRARY / f"{safe_name(title)}{f' ({year})' if year else ''}.md")
    j = lambda s: json.dumps(s, ensure_ascii=False)
    body = f"""---
type: book
subType: ""
title: {j(title)}
englishTitle: {j(english)}
year: {year or 'unknown'}
dataSource: OpenLibraryAPI
url: {j(f'https://openlibrary.org/works/{work}' if work else '')}
id: {j(f'/works/{work}' if work else '')}
author:
{chr(10).join(f'  - {j(a)}' for a in authors)}
category: {j(category)}
plot: unknown
pages: {info.get('Pages', 'unknown')}
image: {j(cover)}
onlineRating: 0
isbn: unknown
isbn13: unknown
released: true
read: {'true' if read else 'false'}
lastRead: ""
personalRating: {rating if rating.isdigit() else 0}
tags: mediaDB/book
---
[[{dest.name}]]
"""
    if note:
        body += f"\n{note}\n"
    fname.write_text(body)
    add_category_section(category)
    update_state(path, "added")

    print(f"\n✅ Ajouté : {fname.name}  →  section {category}")
    subprocess.run(["notify-send", "📚 Bibliothèque", f"{title} ajouté ({category})"])
    if yes("Ouvrir dans Obsidian ?", True):
        rel = fname.relative_to(VAULT).with_suffix("")
        subprocess.Popen(["xdg-open", "obsidian://open?vault=Prime&file=" + urllib.parse.quote(str(rel))],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1)


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "scan":
        cmd_scan()
    elif mode == "init":
        cmd_init()
    elif mode == "add" and len(sys.argv) > 2:
        try:
            cmd_add(sys.argv[2])
        except (KeyboardInterrupt, EOFError):
            update_state(Path(sys.argv[2]), "skipped")
            print("\nAnnulé.")
        except Exception as e:
            print(f"\n❌ Erreur : {e}")
            input("Entrée pour fermer…")
    else:
        print(__doc__)
