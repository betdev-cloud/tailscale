#!/usr/bin/env python3
"""Build GitHub release notes for a Tailscale version from upstream sources."""

import argparse
import os
import sys

import requests

from github_utils import (
    CHANGELOG_URL,
    UPSTREAM_OWNER,
    UPSTREAM_REPO,
    github_session,
    list_tags,
    normalize_tag,
    previous_release_tag,
)


def fetch_upstream_release_body(tag_name, session):
    response = session.get(
        f"https://api.github.com/repos/{UPSTREAM_OWNER}/{UPSTREAM_REPO}/releases/tags/{tag_name}"
    )
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return (response.json().get("body") or "").strip() or None


def fetch_compare_section(tag_name, base_tag, session):
    response = session.get(
        f"https://api.github.com/repos/{UPSTREAM_OWNER}/{UPSTREAM_REPO}/compare/{base_tag}...{tag_name}"
    )
    response.raise_for_status()
    data = response.json()
    commits = data.get("commits") or []

    lines = [f"## Changes since {base_tag}", ""]
    if not commits:
        lines.append("_No commits found between these tags._")
        return "\n".join(lines)

    for commit in commits:
        message = commit["commit"]["message"].splitlines()[0]
        sha = commit["sha"][:7]
        lines.append(f"- {message} ({sha})")

    return "\n".join(lines)


def build_release_notes(version, token=None):
    tag_name = normalize_tag(version)
    session = github_session(token)
    sections = [f"# Tailscale {tag_name}", ""]

    upstream_body = fetch_upstream_release_body(tag_name, session)
    if upstream_body:
        sections.extend(["## Upstream release notes", "", upstream_body, ""])

    tags = list_tags(UPSTREAM_OWNER, UPSTREAM_REPO, session)
    base_tag = previous_release_tag(tag_name, tags)
    if base_tag:
        sections.append(fetch_compare_section(tag_name, base_tag, session))
        sections.append("")
    else:
        sections.append("_Could not determine the previous stable tag for a diff._")
        sections.append("")

    sections.extend(
        [
            "---",
            f"Official changelog: {CHANGELOG_URL}",
            f"Upstream tag: https://github.com/{UPSTREAM_OWNER}/{UPSTREAM_REPO}/tree/{tag_name}",
            f"Compare: https://github.com/{UPSTREAM_OWNER}/{UPSTREAM_REPO}/compare/{base_tag}...{tag_name}"
            if base_tag
            else f"Upstream releases: https://github.com/{UPSTREAM_OWNER}/{UPSTREAM_REPO}/releases",
        ]
    )
    return "\n".join(sections)


def main():
    parser = argparse.ArgumentParser(
        description="Fetch Tailscale release notes from the upstream repository."
    )
    parser.add_argument("version", help="Tailscale version tag, e.g. v1.102.3")
    parser.add_argument(
        "-o",
        "--output",
        help="Write release notes to a file instead of stdout",
    )
    args = parser.parse_args()

    notes = build_release_notes(args.version, os.getenv("GITHUB_TOKEN"))

    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(notes)
    else:
        print(notes)


if __name__ == "__main__":
    try:
        main()
    except requests.HTTPError as error:
        print(error, file=sys.stderr)
        if error.response is not None:
            print(error.response.text, file=sys.stderr)
        sys.exit(1)
