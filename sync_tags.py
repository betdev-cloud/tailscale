#!/usr/bin/env python3
"""Mirror upstream Tailscale release tags into this fork and trigger builds."""

import os
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
    response = session.post(
        f"https://api.github.com/repos/{FORK_OWNER}/{FORK_REPO}/git/refs",
        json={"ref": f"refs/tags/{tag_name}", "sha": sha},
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


def sync_tags(token=None):
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
    created = create_fork_tag(latest_tag, upstream_sha, session)
    if created:
        print(f"Created tag {latest_tag} at upstream commit {upstream_sha[:7]}")
        trigger_build(latest_tag, session)
        print(f"Triggered build for {latest_tag}")
    else:
        print(f"Tag {latest_tag} already exists")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(sync_tags(os.getenv("GITHUB_TOKEN")))
    except requests.HTTPError as error:
        print(error, file=sys.stderr)
        if error.response is not None:
            print(error.response.text, file=sys.stderr)
        raise SystemExit(1)
