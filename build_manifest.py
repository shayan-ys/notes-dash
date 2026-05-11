#!/usr/bin/env python3
"""build_manifest.py — clone the notes repo, emit manifest.json + a templated index.html.

Reads env:
  NOTES_REPO_SLUG       owner/repo on GitHub (e.g. "alice/notes-publish") — required
  GITHUB_TOKEN          PAT with read access to the repo (private repos) — optional for public repos
  GITHUB_USERNAME       username matching the token — optional (falls back to "git")
  NOTES_BASE_URL        public URL where notes are served (e.g. "https://notes.example.com") — required
  NOTES_SITE_TITLE      display title (falls back to host of NOTES_BASE_URL)
  NOTES_UNPUBLISH_CMD   optional command template with {slug}; when set, each row shows a "copy" button
  NOTES_FOOTER_HOST     optional footer-right host:port label
  NOTES_REPO_DIR        local clone path (default /var/lib/notes-dash/repo)
  NOTES_OUT_DIR         output dir served by the http server (default /var/lib/notes-dash/public)
  NOTES_LEDGER_PATH     path to the ledger inside the repo (default .ledger.json)
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse


REPO_DIR = Path(os.environ.get("NOTES_REPO_DIR", "/var/lib/notes-dash/repo"))
OUT_DIR = Path(os.environ.get("NOTES_OUT_DIR", "/var/lib/notes-dash/public"))
LEDGER_REL = os.environ.get("NOTES_LEDGER_PATH", ".ledger.json")
TEMPLATE = Path(__file__).parent / "index.html"


def repo_url() -> str:
    slug = os.environ.get("NOTES_REPO_SLUG")
    if not slug:
        sys.exit("error: NOTES_REPO_SLUG is required (e.g. alice/notes-publish)")
    token = os.environ.get("GITHUB_TOKEN", "")
    user = os.environ.get("GITHUB_USERNAME", "git")
    if token:
        return f"https://{user}:{token}@github.com/{slug}.git"
    return f"https://github.com/{slug}.git"


def site_config() -> dict[str, str]:
    base = os.environ.get("NOTES_BASE_URL", "").rstrip("/")
    if not base:
        sys.exit("error: NOTES_BASE_URL is required (e.g. https://notes.example.com)")
    title = os.environ.get("NOTES_SITE_TITLE") or urlparse(base).netloc
    return {
        "baseUrl": base,
        "siteTitle": title,
        "unpublishCmd": os.environ.get("NOTES_UNPUBLISH_CMD", ""),
        "footerHost": os.environ.get("NOTES_FOOTER_HOST", ""),
    }


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.chunks: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip:
            self.chunks.append(data)

    def text(self) -> str:
        return " ".join(" ".join(self.chunks).split())


def sync_repo() -> None:
    if (REPO_DIR / ".git").exists():
        subprocess.run(["git", "-C", str(REPO_DIR), "fetch", "--quiet", "origin"], check=True)
        subprocess.run(["git", "-C", str(REPO_DIR), "reset", "--hard", "--quiet", "origin/HEAD"], check=True)
    else:
        REPO_DIR.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", "--quiet", repo_url(), str(REPO_DIR)], check=True)


def load_ledger() -> dict[str, dict]:
    ledger_path = REPO_DIR / LEDGER_REL
    if not ledger_path.exists():
        return {}
    return json.loads(ledger_path.read_text())


def page_text(slug: str) -> str:
    html_path = REPO_DIR / slug / "index.html"
    if not html_path.exists():
        return ""
    p = TextExtractor()
    p.feed(html_path.read_text(encoding="utf-8", errors="replace"))
    return p.text()


def render_index(config: dict[str, str]) -> str:
    template = TEMPLATE.read_text(encoding="utf-8")
    inject = (
        f"<script>window.__NOTES_DASH__={json.dumps(config, ensure_ascii=False)};</script>"
    )
    marker = "<!-- __NOTES_DASH_CONFIG__ -->"
    if marker not in template:
        sys.exit(f"error: index.html missing marker {marker}")
    return template.replace(marker, inject, 1)


def build() -> int:
    sync_repo()
    ledger = load_ledger()
    entries = [
        {
            "slug": slug,
            "title": meta.get("title", slug),
            "created": meta.get("created"),
            "updated": meta.get("updated") or meta.get("created"),
            "text": page_text(slug),
        }
        for slug, meta in ledger.items()
    ]
    entries.sort(key=lambda e: e["updated"] or "", reverse=True)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "manifest.json").write_text(json.dumps(entries, ensure_ascii=False))
    (OUT_DIR / "index.html").write_text(render_index(site_config()), encoding="utf-8")
    favicon = TEMPLATE.parent / "favicon.svg"
    if favicon.exists():
        shutil.copyfile(favicon, OUT_DIR / "favicon.svg")

    now_ts = datetime.now(tz=timezone.utc).timestamp()
    week_ago = now_ts - 7 * 86400

    published_this_week = 0
    latest_ts: float | None = None
    for e in entries:
        created_str = e.get("created")
        if not created_str:
            continue
        try:
            ts = datetime.fromisoformat(created_str).timestamp()
        except ValueError:
            continue
        if ts >= week_ago:
            published_this_week += 1
        if latest_ts is None or ts > latest_ts:
            latest_ts = ts

    if latest_ts is None:
        last_published = "—"
    else:
        diff = now_ts - latest_ts
        if diff < 60:
            last_published = "just now"
        elif diff < 3600:
            last_published = f"{int(diff // 60)}m ago"
        elif diff < 86400:
            last_published = f"{int(diff // 3600)}h ago"
        elif diff < 30 * 86400:
            last_published = f"{int(diff // 86400)}d ago"
        else:
            last_published = f"{int(diff // (30 * 86400))}mo ago"

    stats = {
        "total_pages": len(entries),
        "published_this_week": published_this_week,
        "last_published": last_published,
    }
    (OUT_DIR / "stats.json").write_text(json.dumps(stats, ensure_ascii=False))

    print(f"built manifest with {len(entries)} pages", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(build())
