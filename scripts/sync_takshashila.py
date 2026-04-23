#!/usr/bin/env python3
"""
sync_takshashila.py — scrape Anupam Manur's content from takshashila.org.in
and update the YAML listing files on the personal website.

Run locally:   pip install requests beautifulsoup4 && python scripts/sync_takshashila.py
"""

from __future__ import annotations

import os
import re
import sys
from urllib.parse import urlparse, urljoin

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

TEAM_PAGE = "https://takshashila.org.in/content/team/anupam-manur.html"

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUBS_YAML  = os.path.join(REPO_ROOT, "publications", "publications.yml")
BLOGS_YAML = os.path.join(REPO_ROOT, "blog", "blog.yml")
OPEDS_YAML = os.path.join(REPO_ROOT, "op-eds", "op-eds.yml")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; TakshashilaSync/1.0; "
        "+https://github.com/anupam-website)"
    )
}

TIMEOUT = 20  # seconds

# ---------------------------------------------------------------------------
# Category inference
# ---------------------------------------------------------------------------

CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "Economic Policy": [
        "economy", "gdp", "growth", "inflation", "monetary", "rbi",
        "interest rate", "fiscal", "demonetis", "recession", "macro",
        "investment", "capital", "market", "employment", "labour",
        "labor", "jobs", "wage", "subsidy", "price", "mrp",
    ],
    "Trade": [
        "trade", "tariff", "export", "import", "fta", "wto",
        "supply chain", "protectionism", "dumping", "quota",
        "trade war", "trade deal", "trade deficit",
    ],
    "Geoeconomics": [
        "geopolit", "geoeconom", "sanction", "swift", "indo-pacific",
        "china", "pakistan", "trump", "g20", "ipef", "quad",
        "foreign policy", "bilateral", "multilateral",
        "india-us", "india-eu", "brexit", "diplomac",
    ],
    "Public Finance": [
        "budget", "finance commission", "tax", "gst", "pension",
        "expenditure", "revenue", "deficit", "public debt",
        "fiscal policy", "government spend",
    ],
    "Technology Policy": [
        "technology", "digital", "cyber", "fintech", "internet",
        "data", "electronics", "laptop", "semiconductor", "chip",
        "5g", "telecom", "software", "cashless", "payment",
        "artificial intelligence", " ai ",
    ],
    "Platform Economics": [
        "platform", "uber", "ola", "amazon", "flipkart", "swiggy",
        "zomato", "gig worker", "gig economy", "e-commerce",
        "ecommerce", "aggregator", "marketplace", "surge pricing",
        "food delivery", "ride-hailing", "app-based",
    ],
    "Bioeconomy": [
        "bioeconomy", "pharma", "drug", "medicine", "health",
        "vaccine", "e-cigarette", "ivf", "stent", "medical",
        "hospital", "e-pharmacy", "clinical trial",
    ],
    # "Public Policy" is the fallback — no keywords needed
}

# Takshashila category strings → canonical category names
TAKS_CATEGORY_MAP: dict[str, str] = {
    "economic policy": "Economic Policy",
    "economy": "Economic Policy",
    "macroeconomics": "Economic Policy",
    "trade": "Trade",
    "trade policy": "Trade",
    "geoeconomics": "Geoeconomics",
    "geopolitics": "Geoeconomics",
    "foreign policy": "Geoeconomics",
    "public finance": "Public Finance",
    "technology policy": "Technology Policy",
    "technology": "Technology Policy",
    "artificial intelligence": "Technology Policy",
    "ai": "Technology Policy",
    "platform economics": "Platform Economics",
    "digital economy": "Platform Economics",
    "bioeconomy": "Bioeconomy",
    "health": "Bioeconomy",
    "public policy": "Public Policy",
}

# Domain → publication name (sourced from Anupam's op-eds page)
DOMAIN_MAP: dict[str, str] = {
    # Primary outlets
    "indianexpress.com": "Indian Express",
    "timesofindia.indiatimes.com": "Times of India",
    "moneycontrol.com": "Moneycontrol",
    "hindustantimes.com": "Hindustan Times",
    "thehindu.com": "The Hindu",
    "livemint.com": "Mint",
    "deccanherald.com": "Deccan Herald",
    "theprint.in": "The Print",
    "firstpost.com": "Firstpost",
    "ndtv.com": "NDTV",
    "news18.com": "News18",
    # Business / financial
    "businesstoday.in": "Business Today",
    "bloombergquint.com": "Bloomberg Quint",
    "financialexpress.com": "Financial Express",
    "archive.financialexpress.com": "Financial Express",
    # Regional / vernacular
    "prajavani.net": "Prajavani",
    "deccanchronicle.com": "Deccan Chronicle",
    "naiduniaepaper.jagran.com": "Naiduniya",
    "bangalore.citizenmatters.in": "Citizen Matters",
    "citizenmatters.in": "Citizen Matters",
    # Digital-native
    "scroll.in": "Scroll",
    "thereel.scroll.in": "Scroll",
    "thequint.com": "The Quint",
    "factordaily.com": "Factor Daily",
    "thedialogue.co": "The Dialogue",
    # Policy / opinion platforms
    "thinkpragati.com": "Pragati",
    "nationalinterest.in": "Pragati",
    "pragati.nationalinterest.in": "Pragati",
    # International
    "asiaglobalonline.hku.hk": "AsiaGlobal Online",
    # Blogs
    "medium.com": "Medium",
}


def infer_categories(title: str, taks_cats: list[str] | None = None) -> list[str]:
    """Return up to 2 canonical categories for a title string."""
    title_lower = title.lower()
    matched: list[str] = []

    # First try Takshashila's own categories (already mapped)
    if taks_cats:
        for tc in taks_cats:
            canon = TAKS_CATEGORY_MAP.get(tc.lower().strip())
            if canon and canon not in matched:
                matched.append(canon)

    # Then keyword-match on title
    for cat, keywords in CATEGORY_KEYWORDS.items():
        if cat in matched:
            continue
        if any(kw in title_lower for kw in keywords):
            matched.append(cat)
        if len(matched) >= 2:
            break

    return matched[:2] if matched else ["Public Policy"]


def pub_name_from_url(url: str) -> str:
    """Infer publication name from a URL's domain."""
    hostname = urlparse(url).hostname or ""
    # Strip leading www. for lookup
    for key in [hostname, hostname.replace("www.", "")]:
        if key in DOMAIN_MAP:
            return DOMAIN_MAP[key]
    # Fallback: capitalise the second-level domain
    parts = hostname.split(".")
    if len(parts) >= 2:
        return parts[-2].capitalize()
    return hostname


# ---------------------------------------------------------------------------
# YAML helpers  (no PyYAML — write raw strings to preserve comments)
# ---------------------------------------------------------------------------

def normalize_url(url: str) -> str:
    """Normalise a URL for deduplication: https, no www., no -amp suffix, no trailing slash."""
    url = url.strip()
    # Upgrade http → https
    url = re.sub(r"^http://", "https://", url)
    # Remove -amp before .html
    url = re.sub(r"-amp(\.html)$", r"\1", url)
    # Remove www.
    url = re.sub(r"^(https://)www\.", r"\1", url)
    # Remove trailing slash
    url = url.rstrip("/")
    return url


def read_existing_paths(yaml_path: str) -> set[str]:
    """Collect normalised 'path:' values from an existing YAML file."""
    paths: set[str] = set()
    if not os.path.exists(yaml_path):
        return paths
    with open(yaml_path, encoding="utf-8") as fh:
        for line in fh:
            m = re.match(r'\s*path:\s*"?([^"#\n]+)"?', line)
            if m:
                paths.add(normalize_url(m.group(1).strip().strip('"').strip("'")))
    return paths


def read_file_header(yaml_path: str) -> str:
    """Return the comment block at the top of a YAML file (before the first '- ')."""
    header_lines: list[str] = []
    if not os.path.exists(yaml_path):
        return ""
    with open(yaml_path, encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("- "):
                break
            header_lines.append(line)
    return "".join(header_lines)


def read_existing_entries(yaml_path: str) -> str:
    """Return everything from the first '- ' line onwards."""
    if not os.path.exists(yaml_path):
        return ""
    with open(yaml_path, encoding="utf-8") as fh:
        content = fh.read()
    idx = content.find("\n- ")
    if idx == -1:
        idx = content.find("- ")
        if idx == -1:
            return ""
    return content[idx:].lstrip("\n")


def entry_to_yaml(entry: dict) -> str:
    """Serialise one entry dict to a YAML block string."""
    cats = entry.get("categories", ["Public Policy"])
    cats_str = ", ".join(cats)
    title = entry["title"].replace('"', '\\"')
    desc  = entry["description"].replace('"', '\\"')
    path  = entry["path"]
    date  = entry["date"]
    return (
        f'- title: "{title}"\n'
        f'  date: {date}\n'
        f'  description: "{desc}"\n'
        f'  path: "{path}"\n'
        f'  categories: [{cats_str}]\n'
    )


def prepend_entries(yaml_path: str, new_entries: list[dict]) -> int:
    """Prepend new_entries to yaml_path. Returns number added."""
    if not new_entries:
        return 0

    header  = read_file_header(yaml_path)
    existing = read_existing_entries(yaml_path)

    new_blocks = "\n".join(entry_to_yaml(e) for e in new_entries)
    content = header + new_blocks + "\n" + existing

    with open(yaml_path, "w", encoding="utf-8") as fh:
        fh.write(content)

    return len(new_entries)


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def get_soup(url: str) -> BeautifulSoup | None:
    """Fetch a URL and return a BeautifulSoup, or None on error."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")
    except Exception as exc:
        print(f"  [WARN] Could not fetch {url}: {exc}")
        return None


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------

def date_from_slug(url: str) -> str | None:
    """Try to parse YYYYMMDD from the URL slug, return YYYY-MM-DD or None."""
    slug = url.rstrip("/").split("/")[-1]
    m = re.match(r"(\d{4})(\d{2})(\d{2})", slug)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return None


def parse_listing_date(text: str) -> str:
    """
    Parse a date string like 'January 23, 2026' or '2026-01-23' into YYYY-MM-DD.
    Returns the raw text unchanged if parsing fails.
    """
    text = text.strip()
    # Already ISO
    if re.match(r"\d{4}-\d{2}-\d{2}", text):
        return text[:10]
    # 'Month D, YYYY' or 'Month DD, YYYY'
    m = re.match(
        r"(\w+)\s+(\d{1,2}),?\s+(\d{4})", text
    )
    if m:
        months = {
            "january": "01", "february": "02", "march": "03",
            "april": "04", "may": "05", "june": "06",
            "july": "07", "august": "08", "september": "09",
            "october": "10", "november": "11", "december": "12",
        }
        mn = months.get(m.group(1).lower())
        if mn:
            return f"{m.group(3)}-{mn}-{m.group(2).zfill(2)}"
    return text


# ---------------------------------------------------------------------------
# Scrape individual publication page for rich metadata
# ---------------------------------------------------------------------------

def scrape_pub_page(url: str) -> dict | None:
    """Fetch a publication's own page and extract rich metadata."""
    soup = get_soup(url)
    if not soup:
        return None

    # Title
    title_el = soup.select_one(".title-case h1") or soup.select_one("h1")
    title = title_el.get_text(strip=True) if title_el else ""

    # Date
    date = ""
    meta_date = soup.find("meta", attrs={"name": "dcterms.date"})
    if meta_date and meta_date.get("content"):
        date = meta_date["content"][:10]
    if not date:
        date = date_from_slug(url) or ""

    # Authors
    author_els = soup.select("#author-links .title-publisher a p")
    authors = [a.get_text(strip=True) for a in author_els if a.get_text(strip=True)]

    # Publication type
    pub_type = ""
    small_els = soup.select("div.small")
    if small_els:
        pub_type = small_els[0].get_text(strip=True)

    # Takshashila's own categories
    cat_els = soup.select(".title-category a")
    taks_cats = [c.get_text(strip=True) for c in cat_els]

    return {
        "title": title,
        "date": date,
        "authors": authors,
        "pub_type": pub_type,
        "taks_cats": taks_cats,
    }


# ---------------------------------------------------------------------------
# Build description string for a publication
# ---------------------------------------------------------------------------

def build_pub_description(pub_type: str, authors: list[str]) -> str:
    """
    Build the 'description' field, e.g.
    'Takshashila Discussion Document · with Co-author A and Co-author B'
    """
    co_authors = [a for a in authors if "Anupam" not in a]
    desc = pub_type if pub_type else "Takshashila Publication"
    if co_authors:
        if len(co_authors) == 1:
            co_str = co_authors[0]
        elif len(co_authors) == 2:
            co_str = f"{co_authors[0]} and {co_authors[1]}"
        else:
            co_str = ", ".join(co_authors[:-1]) + f", and {co_authors[-1]}"
        desc += f" · with {co_str}"
    return desc


# ---------------------------------------------------------------------------
# Main scrape steps
# ---------------------------------------------------------------------------

def scrape_publications(soup: BeautifulSoup, existing_paths: set[str]) -> list[dict]:
    """Extract new publications from the team page listing."""
    new_entries: list[dict] = []

    container = soup.select_one("#listing-recent-pubs")
    if not container:
        print("  [WARN] Could not find #listing-recent-pubs on team page")
        return new_entries

    for card in container.select(".content-card"):
        # The <a href> wraps the .content-card div, so look at the parent, not inside
        parent = card.parent
        if parent.name != "a" or not parent.get("href"):
            continue
        href = urljoin(TEAM_PAGE, parent.get("href", ""))
        href = normalize_url(href)

        if href in existing_paths:
            continue  # already known

        print(f"  [PUB] New: {href}")
        meta = scrape_pub_page(href)
        if not meta or not meta.get("title"):
            # Fallback from listing
            title_el = card.select_one("h2.content-title") or card.select_one("h2")
            title = title_el.get_text(strip=True) if title_el else parent.get_text(strip=True)
            date  = date_from_slug(href) or ""
            meta  = {"title": title, "date": date, "authors": [], "pub_type": "", "taks_cats": []}

        categories = infer_categories(meta["title"], meta.get("taks_cats"))
        description = build_pub_description(meta.get("pub_type", ""), meta.get("authors", []))

        new_entries.append({
            "title":       meta["title"],
            "date":        meta["date"],
            "description": description,
            "path":        href,
            "categories":  categories,
        })

    return new_entries


def scrape_blogs(soup: BeautifulSoup, existing_paths: set[str]) -> list[dict]:
    """Extract new blog posts from the team page listing."""
    new_entries: list[dict] = []

    # Try multiple container selectors (Takshashila may change structure)
    container = (
        soup.select_one("#listing-recent-blogs")
        or soup.select_one("#recent-blogs")
        or soup.select_one(".recent-blogs")
    )
    if not container:
        # Fallback: find by heading text
        for heading in soup.find_all(["h2", "h3", "h4"]):
            if "blog" in heading.get_text().lower():
                container = heading.find_next_sibling() or heading.parent
                break
    if not container:
        print("  [WARN] Could not find blogs section on team page")
        return new_entries

    for item in container.select(".listing-item, article, .quarto-post, .content-card"):
        # Author filter — only include posts by Anupam
        author_el = item.select_one(".listing-author, .listing-authors")
        if author_el:
            author_text = author_el.get_text()
            if "Anupam" not in author_text:
                continue

        link_el = item.select_one(".listing-title a") or item.select_one("a[href]")
        if not link_el:
            continue
        href = normalize_url(urljoin(TEAM_PAGE, link_el.get("href", "")))

        if href in existing_paths:
            continue

        title_el = item.select_one(".listing-title")
        title = title_el.get_text(strip=True) if title_el else link_el.get_text(strip=True)

        date_el = item.select_one(".listing-date")
        date_raw = date_el.get_text(strip=True) if date_el else ""
        date = parse_listing_date(date_raw) if date_raw else (date_from_slug(href) or "")

        # Check if co-authored (for description)
        description = "Takshashila Institution"
        if author_el:
            all_authors = [
                a.strip() for a in re.split(r",|and", author_el.get_text())
                if a.strip() and "Anupam" not in a
            ]
            if all_authors:
                description += " · with " + ", ".join(all_authors)

        categories = infer_categories(title)

        print(f"  [BLOG] New: {href}")
        new_entries.append({
            "title":       title,
            "date":        date,
            "description": description,
            "path":        href,
            "categories":  categories,
        })

    return new_entries


def scrape_opeds(soup: BeautifulSoup, existing_paths: set[str]) -> list[dict]:
    """Extract new op-eds from the team page 'In the News' listing."""
    new_entries: list[dict] = []

    container = soup.select_one("#listing-recent-news")
    if not container:
        print("  [WARN] Could not find #listing-recent-news on team page")
        return new_entries

    for item in container.select(".listing-item, article, .quarto-post"):
        # Author filter
        author_el = item.select_one(".listing-author, .listing-authors")
        if author_el:
            if "Anupam" not in author_el.get_text():
                continue

        link_el = item.select_one(".listing-title a") or item.select_one("a[href]")
        if not link_el:
            continue
        href = normalize_url(urljoin(TEAM_PAGE, link_el.get("href", "")))

        if href in existing_paths:
            continue

        title_el = item.select_one(".listing-title")
        title = title_el.get_text(strip=True) if title_el else link_el.get_text(strip=True)

        date_el = item.select_one(".listing-date")
        date_raw = date_el.get_text(strip=True) if date_el else ""
        date = parse_listing_date(date_raw) if date_raw else ""

        description = pub_name_from_url(href)
        categories  = infer_categories(title)

        print(f"  [OPED] New: {href}")
        new_entries.append({
            "title":       title,
            "date":        date,
            "description": description,
            "path":        href,
            "categories":  categories,
        })

    return new_entries


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    print(f"Fetching team page: {TEAM_PAGE}")
    soup = get_soup(TEAM_PAGE)
    if not soup:
        print("ERROR: Could not fetch team page. Exiting.")
        _write_github_output(0, 0, 0)
        sys.exit(0)

    existing_pub_paths  = read_existing_paths(PUBS_YAML)
    existing_blog_paths = read_existing_paths(BLOGS_YAML)
    existing_oped_paths = read_existing_paths(OPEDS_YAML)

    print(f"\nScraping publications (known: {len(existing_pub_paths)})…")
    new_pubs = scrape_publications(soup, existing_pub_paths)

    print(f"\nScraping blogs (known: {len(existing_blog_paths)})…")
    new_blogs = scrape_blogs(soup, existing_blog_paths)

    print(f"\nScraping op-eds (known: {len(existing_oped_paths)})…")
    new_opeds = scrape_opeds(soup, existing_oped_paths)

    # Sort newest-first before prepending
    for lst in (new_pubs, new_blogs, new_opeds):
        lst.sort(key=lambda e: e.get("date", ""), reverse=True)

    print("\nWriting YAML files…")
    n_pubs  = prepend_entries(PUBS_YAML,  new_pubs)
    n_blogs = prepend_entries(BLOGS_YAML, new_blogs)
    n_opeds = prepend_entries(OPEDS_YAML, new_opeds)

    print(
        f"\nDone. Added {n_pubs} publication(s), "
        f"{n_blogs} blog(s), {n_opeds} op-ed(s)."
    )

    _write_github_output(n_pubs, n_blogs, n_opeds)


def _write_github_output(pubs: int, blogs: int, opeds: int) -> None:
    """Write step outputs for GitHub Actions (no-op when not in Actions)."""
    output_file = os.environ.get("GITHUB_OUTPUT")
    if not output_file:
        return
    with open(output_file, "a", encoding="utf-8") as fh:
        fh.write(f"new_pubs={pubs}\n")
        fh.write(f"new_blogs={blogs}\n")
        fh.write(f"new_opeds={opeds}\n")
        fh.write(f"any_new={'true' if (pubs + blogs + opeds) > 0 else 'false'}\n")


if __name__ == "__main__":
    main()
