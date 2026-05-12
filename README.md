# notes-dash

> A tiny, gorgeous, single-page archive index for a "notes" site you publish to GitHub.
> Reads a `.ledger.json` from your notes repo, renders an editorial-archive
> listing with live search, and rebuilds itself every 10 minutes via cron.
> No database, no framework — Python stdlib + `git` + `http.server`.

<img src="https://github.com/shayan-ys/notes-dash/raw/main/.github/preview.png" alt="screenshot" width="720">

## What this is

A drop-in dashboard for anyone who publishes private/unlisted notes as static
HTML to a GitHub repo (typical pattern: `<slug>/index.html` files plus a
manifest at the root). It gives you a single page that lists everything you've
published, with:

- **Editorial typography** — [Fraunces](https://fonts.google.com/specimen/Fraunces) display,
  [Newsreader](https://fonts.google.com/specimen/Newsreader) body,
  [IBM Plex Mono](https://fonts.google.com/specimen/IBM+Plex+Mono) metadata
- **Live search** across titles and full body text
- **Light/dark theme** via `prefers-color-scheme`
- **Numbered entries** with staggered fade-in
- **Optional copy-cmd button** per row (e.g. unpublish helper) — hides itself when not configured
- **Keyboard**: `/` focuses search, `Esc` clears it
- **Mobile-first** — clamp-sized type, responsive grid

The whole thing is one container running [http.server](https://docs.python.org/3/library/http.server.html)
serving two static files (`index.html` + `manifest.json`), rebuilt periodically by a Python script.

## Why I wrote it

I publish private writeups to [notes.shayanys.com](https://notes.shayanys.com)
via a static-site flow (one GitHub repo, one folder per page, an unguessable
22-character slug per URL). After a dozen pages the ad-hoc bookmark list was
unmanageable. The off-the-shelf dashboards (Notion, Linkding, Outline) are all
too heavy for "list the things in this repo with a search box." This is what
that should look like instead.

## Architecture

```
  ┌─────────────────────┐                ┌──────────────────────┐
  │ your notes repo on  │  git clone     │  notes-dash          │
  │ GitHub              │  (re-fetch     │  ─────────────       │
  │                     │  every 10 min) │  build_manifest.py:  │
  │  .ledger.json       │ ─────────────► │   reads ledger,      │
  │  <slug-a>/i.html    │                │   extracts page text,│
  │  <slug-b>/i.html    │                │   writes manifest    │
  └─────────────────────┘                │                      │
                                         │  http.server :8181   │
                                         │   serves:            │
                                         │   - index.html       │
                                         │   - manifest.json    │
                                         └──────────────────────┘
                                                    │
                                                    ▼
                                          browser fetches both,
                                          renders the archive
```

The script expects your notes repo to contain a `.ledger.json` at its root with
this shape:

```json
{
  "bX3nQyuYdw3YmTf65XVGDQ": {
    "title": "Some Note Title",
    "created": "2026-05-11T12:34:56Z",
    "updated": "2026-05-11T12:34:56Z"
  },
  "another-slug": { ... }
}
```

…and one `<slug>/index.html` file per entry. The dashboard pulls plain text
from each page so the search box covers body content, not just titles.

## Run with Docker Compose

```bash
git clone https://github.com/shayan-ys/notes-dash.git
cd notes-dash
cp .env.example .env
# edit .env — minimum: NOTES_REPO_SLUG and NOTES_BASE_URL
docker compose up -d --build
open http://localhost:8181
```

That's it. The container clones your notes repo into a named volume, rebuilds
the manifest every 10 minutes, and serves the dashboard on port 8181.

## Configuration

All config is via env vars (see [`.env.example`](.env.example) for the full list):

| Variable | Required | Description |
|---|---|---|
| `NOTES_REPO_SLUG` | **yes** | `owner/repo` on GitHub holding your notes |
| `NOTES_BASE_URL` | **yes** | Public URL where notes are served. Each row links to `<base>/<slug>/` |
| `GITHUB_TOKEN` | private repos | Fine-grained PAT with `Contents: read` on the notes repo |
| `GITHUB_USERNAME` | private repos | Username matching the PAT |
| `NOTES_SITE_TITLE` | no | Masthead text. Defaults to the host of `NOTES_BASE_URL`. Include a `.` to get the italic accent. |
| `NOTES_UNPUBLISH_CMD` | no | Template with `{slug}` placeholder. When set, each row shows a "copy" button. |
| `NOTES_FOOTER_HOST` | no | Small label in the footer right (e.g. your homelab hostname) |
| `NOTES_LEDGER_PATH` | no | Path to ledger inside the repo (default `.ledger.json`) |
| `PORT` | no | Host port to bind (default `8181`) |

## Run without Docker

```bash
pip install --user --break-system-packages -r requirements.txt   # no deps; stdlib only
export NOTES_REPO_SLUG=you/your-notes
export NOTES_BASE_URL=https://notes.you.com
export NOTES_REPO_DIR=/tmp/notes-repo
export NOTES_OUT_DIR=/tmp/notes-public
python3 build_manifest.py
cd /tmp/notes-public && python3 -m http.server 8181
```

## Security note

The dashboard is intentionally `noindex,nofollow`. It's designed to live behind
your VPN / Meshnet / private network, not on the open internet — your notes' slugs
are the access tokens, and exposing them in a manifest is fine *only* in a
trusted-network context. If you want public discovery, that's a different tool.

## Companion: the publish side

`notes-dash` only *reads* a ledger. The matching write-side flow lives at
[shayan-ys/notes-publisher](https://github.com/shayan-ys/notes-publisher) — a small
CLI that takes an HTML writeup, generates a 22-char slug, commits the rendered
page into a notes-content repo, and updates `.ledger.json`. Either flow works on
its own; together they're a complete private-publishing pipeline.

## License

MIT — see [LICENSE](LICENSE).
