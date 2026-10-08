---
cssclasses:
  - library
---
## 💻 Informatique

```dataview
TABLE WITHOUT ID
  choice(!image, "", choice(startswith(image, "http"), "![|80](" + image + ")", embed(link(image)))) AS Couverture,
  file.link AS Titre,
  author AS Auteur,
  year AS Année,
  choice(read, "✅", "📖") AS Lu,
  choice(personalRating > 0, personalRating + "/10", "—") AS Note
FROM "02 - Education/Library"
WHERE type = "book" AND category = "Informatique"
SORT read ASC, year DESC
```

## 🔭 Science

```dataview
TABLE WITHOUT ID
  choice(!image, "", choice(startswith(image, "http"), "![|80](" + image + ")", embed(link(image)))) AS Couverture,
  file.link AS Titre,
  author AS Auteur,
  year AS Année,
  choice(read, "✅", "📖") AS Lu,
  choice(personalRating > 0, personalRating + "/10", "—") AS Note
FROM "02 - Education/Library"
WHERE type = "book" AND category = "Science"
SORT read ASC, year DESC
```

## 📚 Littérature

```dataview
TABLE WITHOUT ID
  choice(!image, "", choice(startswith(image, "http"), "![|80](" + image + ")", embed(link(image)))) AS Couverture,
  file.link AS Titre,
  author AS Auteur,
  year AS Année,
  choice(read, "✅", "📖") AS Lu,
  choice(personalRating > 0, personalRating + "/10", "—") AS Note
FROM "02 - Education/Library"
WHERE type = "book" AND category = "Littérature"
SORT read ASC, year DESC
```

## 🌱 Développement personnel

```dataview
TABLE WITHOUT ID
  choice(!image, "", choice(startswith(image, "http"), "![|80](" + image + ")", embed(link(image)))) AS Couverture,
  file.link AS Titre,
  author AS Auteur,
  year AS Année,
  choice(read, "✅", "📖") AS Lu,
  choice(personalRating > 0, personalRating + "/10", "—") AS Note
FROM "02 - Education/Library"
WHERE type = "book" AND category = "Développement personnel"
SORT read ASC, year DESC
```
