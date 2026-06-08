#!/usr/bin/env python3
"""
Scrape the latest IPPR issue, download the cover image, and update ippr.qmd.
Outputs changed=true/false to $GITHUB_OUTPUT (for GitHub Actions).

Usage:
    python scripts/sync_ippr.py
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

REPO = Path(__file__).parent.parent
IPPR_QMD = REPO / "ippr.qmd"
COVER_IMAGE = REPO / "images" / "ippr-current-issue.png"
CURRENT_URL = "https://ippr.in/index.php/ippr/issue/current"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; anupammanur-sync/1.0)"}


# ── Scraping helpers ───────────────────────────────────────────────

def get_soup(url: str) -> tuple[BeautifulSoup, str]:
    """Fetch URL and return (BeautifulSoup, final_url_after_redirects)."""
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    resp.encoding = "utf-8"
    return BeautifulSoup(resp.text, "html.parser"), resp.url


def extract_issue_info(soup: BeautifulSoup, issue_url: str) -> tuple[str, str, str, str, str]:
    """Return (vol_label, issue_id, issue_url, cover_url, description)."""

    # --- Volume/issue label ---
    # OJS renders "Vol. X No. Y (YYYY): Indian Public Policy Review"
    # Try multiple selectors since IPPR may use a custom theme
    vol_label = ""
    for selector in ["h1.page_title", ".page_title", "h1", ".issue-title"]:
        el = soup.select_one(selector)
        if el:
            text = el.get_text(strip=True)
            if re.search(r"Vol\.\s*\d+", text):
                vol_label = re.sub(r":\s*Indian Public Policy Review.*", "", text).strip()
                break
    # Fallback: extract from <title> tag or breadcrumb
    if not vol_label:
        title_tag = soup.find("title")
        if title_tag:
            text = title_tag.get_text(strip=True)
            m = re.search(r"(Vol\.\s*\d+\s*No\.\s*\d+\s*\(\d{4}\))", text)
            if m:
                vol_label = m.group(1)
    # Fallback: extract from breadcrumb last item
    if not vol_label:
        crumbs = soup.select(".breadcrumb li, nav[aria-label] li, ol.breadcrumb li")
        for crumb in reversed(crumbs):
            text = crumb.get_text(strip=True)
            if re.search(r"Vol\.\s*\d+", text):
                vol_label = re.sub(r":\s*Indian Public Policy Review.*", "", text).strip()
                break
    if not vol_label:
        vol_label = "Current Issue"

    # --- Issue ID from URL ---
    m = re.search(r"/issue/view/(\d+)", issue_url)
    issue_id = m.group(1) if m else "0"

    # --- Cover image URL ---
    cover_img = soup.select_one(".cover img") or soup.select_one("img.img-fluid")
    if cover_img and cover_img.get("src"):
        cover_url = cover_img["src"]
        if not cover_url.startswith("http"):
            cover_url = "https://ippr.in" + cover_url
    else:
        # Fallback: OJS public cover image path
        cover_url = f"https://ippr.in/public/journals/1/cover_issue_{issue_id}_en_US.png"

    # --- Description: OJS issue description or article-list fallback ---
    desc_el = (
        soup.select_one(".issue_description")
        or soup.select_one(".description")
    )
    if desc_el:
        description = " ".join(desc_el.get_text(" ", strip=True).split())
    else:
        articles = soup.select(".obj_article_summary .title")
        if articles:
            titles = [a.get_text(strip=True) for a in articles]
            n = len(titles)
            listed = "; ".join(f'"{t}"' for t in titles[:4])
            tail = "." if n <= 4 else "; and more."
            description = (
                f"This edition features {n} contribution{'s' if n != 1 else ''} "
                f"on Indian public policy. Topics include: {listed}{tail}"
            )
        else:
            description = (
                "Visit the issue page to browse all articles in this edition."
            )

    return vol_label, issue_id, issue_url, cover_url, description


# ── File operations ────────────────────────────────────────────────

def download_cover(cover_url: str) -> None:
    resp = requests.get(cover_url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    COVER_IMAGE.write_bytes(resp.content)
    print(f"  Downloaded cover image ({len(resp.content) // 1024} KB) → {COVER_IMAGE.name}")


def build_block(vol_label: str, issue_url: str, description: str) -> str:
    return (
        f"<!-- IPPR_AUTO_START -->\n"
        f"## Current Issue — {vol_label}\n"
        f"\n"
        f"```{{=html}}\n"
        f'<div style="text-align:center;margin:2rem 0;">\n'
        f'  <a href="{issue_url}" target="_blank">\n'
        f'    <img src="images/ippr-current-issue.png"'
        f' alt="IPPR {vol_label} Cover"'
        f' style="max-width:350px;width:100%;border-radius:6px;box-shadow:0 4px 16px rgba(0,0,0,0.12);">\n'
        f"  </a>\n"
        f"</div>\n"
        f"```\n"
        f"\n"
        f"{description}\n"
        f"\n"
        f"[Read the full issue →]({issue_url}){{.btn .btn-outline-primary target=\"_blank\"}}\n"
        f"<!-- IPPR_AUTO_END -->"
    )


def update_qmd(new_block: str) -> bool:
    text = IPPR_QMD.read_text(encoding="utf-8")
    pattern = r"<!-- IPPR_AUTO_START -->.*?<!-- IPPR_AUTO_END -->"
    new_text, count = re.subn(pattern, new_block, text, flags=re.DOTALL)
    if count == 0:
        print("ERROR: sentinel markers not found in ippr.qmd", file=sys.stderr)
        sys.exit(1)
    if new_text == text:
        print("  ippr.qmd already up to date — no changes written.")
        return False
    IPPR_QMD.write_text(new_text, encoding="utf-8")
    print("  ippr.qmd updated.")
    return True


def set_output(key: str, value: str) -> None:
    gho = os.environ.get("GITHUB_OUTPUT")
    if gho:
        with open(gho, "a") as f:
            f.write(f"{key}={value}\n")


# ── Main ───────────────────────────────────────────────────────────

def main() -> None:
    print(f"Fetching current IPPR issue from {CURRENT_URL} ...")
    soup, final_url = get_soup(CURRENT_URL)
    vol_label, issue_id, issue_url, cover_url, description = extract_issue_info(soup, final_url)
    print(f"  Latest issue : {vol_label}")
    print(f"  Issue URL    : {issue_url}")
    print(f"  Cover URL    : {cover_url}")

    # Check whether this issue is already in ippr.qmd
    existing = IPPR_QMD.read_text(encoding="utf-8")
    if vol_label in existing and issue_url in existing:
        print("No new issue detected — ippr.qmd is already current.")
        set_output("changed", "false")
        return

    print(f"New issue detected ({vol_label}) — updating …")
    download_cover(cover_url)
    new_block = build_block(vol_label, issue_url, description)
    changed = update_qmd(new_block)
    set_output("changed", "true" if changed else "false")
    print("Done.")


if __name__ == "__main__":
    main()
