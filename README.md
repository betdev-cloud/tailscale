# betdev-cloud/tailscale

A fork repository that automatically mirrors stable [tailscale/tailscale](https://github.com/tailscale/tailscale) release tags, builds Linux binaries from upstream source, and publishes them as GitHub Releases.

## How it works

1. **`sync-tags.yml`** runs on an hourly schedule and checks for new stable tags in the upstream repository.
2. **`sync_tags.py`** mirrors the latest upstream release tag into this fork, pointing to the **upstream commit** rather than `main`.
3. After the tag is created, **`build.yml`** is triggered automatically. It builds `tailscale`, `tailscaled`, `derper`, and `derpprobe` from upstream source and publishes a GitHub Release.

```
upstream tailscale/tailscale
        │
        │  new stable tag detected (hourly)
        ▼
  sync_tags.py
        │
        ├─ mirrors tag → betdev-cloud/tailscale
        │
        └─ dispatches build.yml
                │
                ├─ resolve upstream SHA + Go version
                ├─ generate release notes (fetch_changelog.py)
                └─ build & publish 4 binaries to GitHub Release
```

## Repository structure

| File / Directory | Purpose |
|---|---|
| `sync_tags.py` | Mirrors stable upstream tags into the fork and triggers the build workflow |
| `fetch_changelog.py` | Builds Markdown release notes from upstream GitHub sources |
| `github_utils.py` | Shared GitHub API helpers and constants |
| `tests/test_sync_tags.py` | Unit tests for the sync logic |
| `.github/workflows/sync-tags.yml` | Hourly cron job that runs the tag sync |
| `.github/workflows/build.yml` | Builds binaries and publishes a GitHub Release |

## Requirements

- Python ≥ 3.11
- [uv](https://github.com/astral-sh/uv) package manager
- `GITHUB_TOKEN` with `contents: write` and `actions: write` permissions (provided automatically by GitHub Actions)

Install dependencies locally:

```bash
uv sync
```

## Usage

### Running the tag sync locally

```bash
# Dry-run — shows what would happen without making any changes
uv run python sync_tags.py --dry-run

# Live run — mirrors the tag and triggers build.yml
GITHUB_TOKEN=<token> uv run python sync_tags.py
```

**Dry-run output example:**

```
Latest upstream tag: v1.102.3
[DRY-RUN] Would create tag v1.102.3 at upstream commit abc1234
[DRY-RUN] Would trigger build for v1.102.3
```

### Generating release notes

```bash
# Print to stdout
uv run python fetch_changelog.py v1.102.3

# Save to a file
uv run python fetch_changelog.py v1.102.3 -o release-notes.md
```

**Example output for `v1.102.3`:**

```markdown
# Tailscale v1.102.3

## Changes since v1.102.2

- ipn/ipnlocal,net/dns/resolver: prevent bare name resolution when MagicDNS is disabled (abc1234)
- feature/conn25: don't pre-size flow table maps (def5678)
...

---
Official changelog: https://tailscale.com/changelog
Upstream tag: https://github.com/tailscale/tailscale/tree/v1.102.3
Compare: https://github.com/tailscale/tailscale/compare/v1.102.2...v1.102.3
```

Release notes are assembled from three sources (in order):

1. **GitHub Release body** from `tailscale/tailscale`, if a release already exists for that tag.
2. **Commit list** between the previous stable tag and the current one, fetched via the GitHub Compare API.
3. **Footer links** — official changelog, upstream tag, and diff URL.

### Running unit tests

```bash
uv run python -m unittest discover -s tests -p "test_*.py"
```

### Triggering a manual build

The **`Create and publish artifacts`** workflow can be dispatched manually from the GitHub Actions UI with a `version` input (e.g. `v1.102.3`). This resolves the upstream commit SHA and Go toolchain version, generates release notes, and builds all four binaries.

## GitHub Actions workflows

### `sync-tags.yml` — tag synchronisation

| Trigger | Behaviour |
|---|---|
| `pull_request` (touching sync code) | Dry-run + unit tests only (`contents: read`) |
| `schedule` (hourly) | Live sync with tag push and build dispatch |
| `workflow_dispatch` | Live sync on demand |

The PR job (`sync_tags_dry_run`) runs with read-only permissions and never pushes tags or triggers builds, making it safe to validate changes before merging.

### `build.yml` — binary build and release

Triggered by `workflow_dispatch` with a required `version` input.

**`prepare-release` job:**

1. Resolves the upstream commit SHA for the given tag.
2. Detects the Go toolchain version from the upstream `go.mod`.
3. Generates release notes with `fetch_changelog.py` and uploads them as an artifact.

**`build-and-publish` job (matrix):**

Builds `tailscale`, `tailscaled`, `derper`, and `derpprobe` in parallel. Each binary is compiled from upstream source at the resolved commit SHA using the matching Go version. Version stamps (`-ldflags`) are injected at build time. Binaries are uploaded directly to the GitHub Release for the given tag.

## Module reference

### `github_utils.py`

Shared constants and helper functions used by both scripts.

| Name | Type | Description |
|---|---|---|
| `UPSTREAM_OWNER` | `str` | `tailscale` |
| `UPSTREAM_REPO` | `str` | `tailscale` |
| `FORK_OWNER` | `str` | `betdev-cloud` |
| `FORK_REPO` | `str` | `tailscale` |
| `CHANGELOG_URL` | `str` | `https://tailscale.com/changelog` |
| `github_session(token)` | function | Returns an authenticated `requests.Session` |
| `normalize_tag(version)` | function | Ensures the version string has a `v` prefix |
| `list_tags(owner, repo, session)` | function | Paginates the GitHub Tags API |
| `get_tag_commit_sha(owner, repo, tag, session)` | function | Resolves annotated or lightweight tags to a commit SHA |
| `get_latest_release_tag(owner, repo, session)` | function | Returns the tag name of the latest published release |
| `previous_release_tag(tag, tags)` | function | Finds the preceding stable tag for a diff base |
| `sorted_release_tags(tags)` | function | Filters and sorts tags by semantic version |

### `sync_tags.py`

| Function | Description |
|---|---|
| `sync_tags(token, dry_run)` | Main entry point: compares upstream vs fork tags and syncs if needed |
| `fork_tag_names(session)` | Returns the set of tag names already present in the fork |
| `create_fork_tag(tag_name, sha, session)` | Shallow-fetches the tag from upstream via git and pushes it to the fork |
| `trigger_build(tag_name, session)` | Dispatches `build.yml` with the given version |

### `fetch_changelog.py`

| Function | Description |
|---|---|
| `build_release_notes(version, token)` | Assembles and returns the full Markdown release notes string |
| `fetch_upstream_release_body(tag, session)` | Fetches the body of an upstream GitHub Release, or `None` if not found |
| `fetch_compare_section(tag, base_tag, session)` | Returns a Markdown commit list via the GitHub Compare API |

## Limitations

- **Pre-release tags** (e.g. `-pre`, `-pre1`) are ignored. Only tags matching `v<major>.<minor>.<patch>` are considered stable.
- **Official changelog scraping** is not supported. The tailscale.com/changelog page is client-rendered with no public JSON API, so release notes rely on the GitHub Release body and Compare API instead.
- **Empty release notes**: if upstream has not yet published a GitHub Release for a given tag, the notes will contain only the commit diff and footer links.
- **Tag objects**: upstream tags may be annotated (pointing to a tag object rather than a commit directly). `get_tag_commit_sha` handles both cases by dereferencing annotated tags when needed.
