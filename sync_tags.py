#!/usr/bin/env python3
"""Mirror upstream Tailscale release tags into this fork and trigger builds."""

import argparse
import os
import subprocess
import sys

import requests

from github_utils import (
    FORK_OWNER,
    FORK_REPO,
    UPSTREAM_OWNER,
    UPSTREAM_REPO,
    get_tag_commit_sha,
    github_session,
    list_tags,
    parse_version,
    sorted_release_tags,
)


def fork_tag_names(session):
    tags = list_tags(FORK_OWNER, FORK_REPO, session)
    return {tag["name"] for tag in tags}


def create_fork_tag(tag_name, sha, session):
    # The upstream release tag can point to an object missing from the fork.
    # Mirror the tag through git so the referenced object is transferred too.
    del sha, session
    upstream_url = f"https://github.com/{UPSTREAM_OWNER}/{UPSTREAM_REPO}.git"
    remotes = subprocess.run(
        ["git", "remote"],
        check=True,
        capture_output=True,
        text=True,
    )
    if "upstream" not in remotes.stdout.split():
        subprocess.run(
            ["git", "remote", "add", "upstream", upstream_url],
            check=True,
        )

    subprocess.run(
        ["git", "fetch", "--depth=1", "upstream", f"refs/tags/{tag_name}:refs/tags/{tag_name}"],
        check=True,
    )

    push = subprocess.run(
        ["git", "push", "origin", f"refs/tags/{tag_name}"],
        check=False,
        capture_output=True,
        text=True,
    )
    if push.returncode == 0:
        return True
    if "already exists" in (push.stdout + push.stderr):
        return False
    raise RuntimeError(f"Failed to push tag {tag_name}: {push.stderr or push.stdout}")


def trigger_build(tag_name, session):
    response = session.post(
        f"https://api.github.com/repos/{FORK_OWNER}/{FORK_REPO}/actions/workflows/build.yml/dispatches",
        json={"ref": "main", "inputs": {"version": tag_name}},
    )
    if response.status_code != 204:
        response.raise_for_status()


def sync_tags(token=None, dry_run=False):
    session = github_session(token)

    upstream_tags = list_tags(UPSTREAM_OWNER, UPSTREAM_REPO, session)
    upstream_release_tags = sorted_release_tags(upstream_tags)
    fork_tags = fork_tag_names(session)

    new_tags = [tag for tag in upstream_release_tags if tag not in fork_tags]
    if not new_tags:
        print("No new tags found")
        return 0

    latest_tag = max(new_tags, key=parse_version)
    print(f"Latest new tag: {latest_tag}")

    upstream_sha = get_tag_commit_sha(
        UPSTREAM_OWNER, UPSTREAM_REPO, latest_tag, session
    )
    if dry_run:
        print(
            f"[DRY-RUN] Would create tag {latest_tag} at upstream commit {upstream_sha[:7]}"
        )
        print(f"[DRY-RUN] Would trigger build for {latest_tag}")
        return 0

    created = create_fork_tag(latest_tag, upstream_sha, session)
    if created:
        print(f"Created tag {latest_tag} at upstream commit {upstream_sha[:7]}")
        trigger_build(latest_tag, session)
        print(f"Triggered build for {latest_tag}")
    else:
        print(f"Tag {latest_tag} already exists")

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
