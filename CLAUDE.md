# Pranay Kotasthane — Personal Website

Built with [Quarto](https://quarto.org). Source lives in this repo; the rendered output goes to `_site/`.

---

## How to build and preview

```bash
quarto render          # build everything into _site/
quarto preview         # live preview in browser (auto-reloads on save)
```

---

## How to add content

### 1. Blog post

Create a new `.qmd` file in `blog/`. Filename becomes the URL slug.

```yaml
---
title: "Your Title"
date: "2025-03-01"
description: "One-line summary shown in the listing"
author: "Pranay Kotasthane"
categories:
  - Semiconductor Geopolitics   # use one or more from the canonical list below
---

Your article text here.
```

**Canonical categories (use these consistently):**
- `Semiconductor Geopolitics`
- `Critical Minerals`
- `AI Geopolitics`
- `Technology Policy`
- `Public Policy`
- `Public Finance`
- `Political Economy`
- `India Foreign Policy`

**Optional: pull quote in right margin**
```markdown
::: {.pullquote .column-margin}
A sentence worth highlighting.
:::
```

**Optional: source attribution in left margin** (if the post also appeared in a publication)
```markdown
::: {.source-note .column-margin}
**Mint**
Originally published as part of [The Intersection](url) column.
:::
```

---

### 2. Op-ed — external link only (freely accessible)

Add 5 lines to `op-eds/op-eds.yml`:

```yaml
- title: "Your Article Headline"
  date: 2025-03-01
  description: "The Hindu"
  path: "https://thehindu.com/..."
  categories: [Geopolitics]
```

---

### 3. Op-ed — with full text or excerpt (paywalled content)

Create a new `.qmd` file in `op-eds/`. It will appear in the op-eds listing and also get its own page.

```yaml
---
title: "Your Article Headline"
date: "2025-03-01"
description: "Mint"
categories: [Geopolitics]
---
```

At the top of the body, add the attribution block:

```html
```{=html}
<div class="op-ed-source">
  <div class="op-ed-source-label">Originally published in</div>
  <div class="op-ed-source-pub">Mint</div>
  <a href="https://livemint.com/..." class="op-ed-source-link" target="_blank">Read original →</a>
</div>
```
```

Then paste the article text. For excerpts only, add at the bottom:

```markdown
::: {.read-more-box}
*Excerpt only — the article continues at the original publication.*

[Read the full article at Mint →](https://livemint.com/...){.btn .btn-primary target="_blank"}
:::
```

---

### 4. Publication / paper

Add to `publications/publications.yml`:

```yaml
- title: "Paper or Brief Title"
  date: 2025-03-01
  description: "Takshashila Institution · with Co-author Name"
  path: "https://doi.org/..."
  categories: [Technology Policy]
```

---

### 5. Book

Edit `books.qmd` directly. Each book uses this structure:

```markdown
::: {.book-card}
::: {.grid}
::: {.g-col-3}
![Cover](images/bookname.jpg){.book-cover}
:::
::: {.g-col-9}
### Book Title
**Co-authored with:** Name

*Publisher, Year*

Short description.

[Buy →](url) | [Read excerpt →](url)
:::
:::
:::
```

---

### 6. Course

Edit `courses.qmd` directly. Each course:

```markdown
::: {.course-card}
### Course Name
**Institution:** Takshashila Institution

Description of the course.

[Learn more →](url)
:::
```

---

### 7. Project

Edit `projects.qmd`. Each project:

```markdown
::: {.idea-card}
### Project Name
2–3 sentence description of what you're working on.
:::
```

---

### 8. Big Idea

Edit `big-ideas.qmd`. Same structure as projects:

```markdown
::: {.idea-card}
### Idea Name
2–3 sentence description.
:::
```

---

## Site structure

```
_quarto.yml          # site config, navbar
styles.scss          # all custom CSS
index.qmd            # homepage

blog/
  index.qmd          # blog listing (auto-generates RSS at blog/index.xml)
  your-post.qmd      # one file per post

op-eds/
  index.qmd          # op-eds listing
  op-eds.yml         # external-link-only op-eds
  your-oped.qmd      # op-eds with full/partial text

publications/
  index.qmd          # publications listing
  publications.yml   # all publications

books.qmd
courses.qmd
projects.qmd
big-ideas.qmd
newsletter.qmd
podcast.qmd
```

---

## Workflow: Obsidian → personal site → Takshashila

1. Write in Obsidian
2. Export/convert to `.qmd`
3. Save to `blog/` (or `op-eds/`) in this repo — this is your **canonical copy**
4. Copy the same file to `~/OurWebsite/` if it's also going on the Takshashila site
5. Run `quarto render` and deploy

---

## Colours and fonts

| Role | Value |
|---|---|
| Primary (navy) | `#0D1F3C` |
| Accent (amber) | `#B85C00` |
| Accent light (tint) | `#F5ECE0` |
| Body font | DM Sans (Google Fonts) |
| Heading / body-text font | Playfair Display (Google Fonts) |

To change colours, edit the variables at the top of `styles.scss`.

---

## Deployment (GitHub Actions)

The site is live at **https://pranaykotas.com**, hosted on GitHub Pages.

Two workflows in `.github/workflows/`:

| Workflow | Trigger | What it does |
|---|---|---|
| `deploy.yml` | Every push to `main` | Runs `quarto render`, pushes `_site/` to `gh-pages` branch |
| `sync-takshashila.yml` | Mon + Thu 6am UTC | Scrapes Takshashila team page, adds new content to YAMLs, commits → triggers deploy |

Manual trigger: GitHub → Actions tab → select workflow → Run workflow.

**git push notes** (local quirk on this machine):
```bash
git config http.version HTTP/1.1
git config http.postBuffer 524288000
git push --set-upstream origin main   # first push only
git push                              # subsequent pushes
```

---

## YAML content rules — IMPORTANT

The blog and op-eds listings read **only from their `.yml` files** (not from `*.qmd`).

Rules for all three YAMLs (`blog/blog.yml`, `op-eds/op-eds.yml`, `publications/publications.yml`):

- `path:` must be a full `https://` URL — never a relative path like `../../content/...`
- `date:` must be ISO format `YYYY-MM-DD`
- Add new entries at the **top** of the file
- Editing these files directly in the GitHub web editor can introduce garbled characters (â€™ instead of ') and relative paths — prefer editing locally and pushing

---

## Auto-sync script

`scripts/sync_takshashila.py` — scrapes `takshashila.org.in/content/team/pranay-kotasthane.html` and prepends new entries to the three YAMLs.

Run locally to test:
```bash
python3 -m venv /tmp/venv && /tmp/venv/bin/pip install requests beautifulsoup4
/tmp/venv/bin/python scripts/sync_takshashila.py
```
