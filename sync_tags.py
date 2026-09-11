#!/usr/bin/env python3
"""Mirror upstream Tailscale release tags into this fork and trigger builds."""

import argparse
import os
import sys

import requests

from github_utils import (
    FORK_OWNER,
    FORK_REPO,
    UPSTREAM_OWNER,
    UPSTREAM_REPO,
    get_latest_release_tag,
    get_tag_commit_sha,
    github_session,
    list_tags,
)


def fork_tag_names(session):
    tags = list_tags(FORK_OWNER, FORK_REPO, session)
    return {tag["name"] for tag in tags}


def fork_default_branch_sha(session):
    """Return the commit SHA at the tip of this repository's default branch."""
    repo = session.get(f"https://api.github.com/repos/{FORK_OWNER}/{FORK_REPO}")
    repo.raise_for_status()
    default_branch = repo.json()["default_branch"]

    ref = session.get(
        f"https://api.github.com/repos/{FORK_OWNER}/{FORK_REPO}/git/ref/heads/{default_branch}"
    )
    ref.raise_for_status()
    return ref.json()["object"]["sha"], default_branch


def create_fork_tag(tag_name, target_sha, session):
    # This repository is not a git fork of tailscale/tailscale and does not
    # contain upstream objects. Point the release tag at a commit that already
    # exists here; build.yml resolves the real upstream commit by tag name.
    response = session.post(
        f"https://api.github.com/repos/{FORK_OWNER}/{FORK_REPO}/git/refs",
        json={"ref": f"refs/tags/{tag_name}", "sha": target_sha},
    )
    if response.status_code == 201:
        return True
    if response.status_code == 422 and "Reference already exists" in response.text:
        return False
    response.raise_for_status()
    return True


def trigger_build(tag_name, session):
    response = session.post(
        f"https://api.github.com/repos/{FORK_OWNER}/{FORK_REPO}/actions/workflows/build.yml/dispatches",
        json={"ref": "main", "inputs": {"version": tag_name}},
    )
    if response.status_code != 204:
        response.raise_for_status()


def sync_tags(token=None, dry_run=False):
    session = github_session(token)

    upstream_latest_tag = get_latest_release_tag(UPSTREAM_OWNER, UPSTREAM_REPO, session)
    fork_tags = fork_tag_names(session)

    if upstream_latest_tag in fork_tags:
        print(f"Latest upstream tag {upstream_latest_tag} already exists in fork")
        return 0

    print(f"Latest upstream tag: {upstream_latest_tag}")

    upstream_sha = get_tag_commit_sha(
        UPSTREAM_OWNER, UPSTREAM_REPO, upstream_latest_tag, session
    )
    target_sha, branch = fork_default_branch_sha(session)
    if dry_run:
        print(
            f"[DRY-RUN] Would create tag {upstream_latest_tag} at {branch} ({target_sha[:7]}); "
            f"upstream commit is {upstream_sha[:7]}"
        )
        print(f"[DRY-RUN] Would trigger build for {upstream_latest_tag}")
        return 0

    created = create_fork_tag(upstream_latest_tag, target_sha, session)
    if created:
        print(
            f"Created tag {upstream_latest_tag} at {branch} ({target_sha[:7]}); "
            f"upstream commit is {upstream_sha[:7]}"
        )
        trigger_build(upstream_latest_tag, session)
        print(f"Triggered build for {upstream_latest_tag}")
    else:
        print(f"Tag {upstream_latest_tag} already exists")

    return 0


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Sync stable upstream tags into fork and trigger build workflow."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned actions without creating tags or triggering workflows.",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    try:
        args = parse_args()
        raise SystemExit(sync_tags(os.getenv("GITHUB_TOKEN"), dry_run=args.dry_run))
    except requests.HTTPError as error:
        print(error, file=sys.stderr)
        if error.response is not None:
            print(error.response.text, file=sys.stderr)
        raise SystemExit(1)
