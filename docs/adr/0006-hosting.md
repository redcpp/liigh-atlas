# ADR-0006 — Hosting requirements (LIIGH + public demo host)

Status: Proposed (maintainer gate after Phase 0)

## Context

NFR-2 `[Call][Diego]`: nginx on a public LIIGH server under a subdomain like `atlas.liigh.unam.mx`
(following `vcfplotein.liigh.unam.mx`), HTTPS via Let's Encrypt, quota ≥ 10 GB, plus a public demo
host with dev data. Assets are immutable per release (ADR-0002), ~5.1K per-gene files (ADR-0003) and
tens of thousands of H&E tiles (ADR-0004). Jair administers the server; the maintainer deploys; the
agent never deploys. Whether a public demo may exist before the paper is open (Q10).

## Options

**Server config for LIIGH:** plain nginx static serving with (i) on-the-fly gzip, or (ii)
**precompressed `gzip_static`** (optional brotli if the module exists, Q13).

**Demo host:**
1. **The LIIGH server itself**, dev-data build at the same subdomain until the lab build replaces it.
2. GitHub Pages: free and simple, but ~1 GB site limit and 100 MB file limit; a full dev build
   (~0.6–0.9 GB) is at the edge.
3. Object storage + CDN (e.g. Cloudflare R2/Pages, Netlify): generous, but a third-party account and
   its own cache rules.

## Decision

**LIIGH nginx is the production host and the preferred demo host (option 1), configured as:**

| Concern | Setting |
|---|---|
| HTTPS | Let's Encrypt (certbot), HTTP → HTTPS redirect, HSTS |
| Compression | `gzip_static on` for pipeline-precompressed `.gz`; `gzip on` for text types; brotli if available |
| Range requests | enabled (nginx default for static files); required for packed-shard fallback (ADR-0003) and large downloads |
| Cache | `/data/<dataset>/<release>/` and hashed `/assets/`: `Cache-Control: public, max-age=31536000, immutable`; `index.html`, `releases.json`: `no-cache` |
| MIME | `.webp image/webp`, `.bin/.u8/.u16 application/octet-stream`, `.json application/json` |
| Security headers | CSP `default-src 'self'`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin` |
| Layout | `/srv/atlas/current` symlink → release directory; previous release kept for stable URLs |
| Quota | ≥ 10 GB: current (≤ 5 GB) + previous release |

Deploy is `rsync` of `dist/` into a new release directory then an atomic symlink swap (instant
rollback). If Q10 forbids a LIIGH demo before the paper, option 3 is the fallback for a dev-data demo;
option 2 only for the `fixture` build. `docs/DEPLOY.md` (Phase 6) is written for Jair.

Local verification uses Homebrew nginx with the same config (no Docker VM, BRIEF §9): curl must show
`206` on a range request, `Content-Encoding: gzip`, and the cache headers.

## Consequences

- No application server, database or runtime: NFR-1 holds by construction.
- Old releases cost disk, bounded by the ≥ 10 GB quota; release retention policy is Jair's call.
- File counts (~5K genes + tiles per release) and module availability go to Jair as Q13.

**Building block:** CDN/static origin with HTTP caching, compression and blue-green (symlink) deploys.
