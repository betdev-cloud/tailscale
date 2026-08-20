import os
import re
from functools import cmp_to_key

import requests

UPSTREAM_OWNER = "tailscale"
UPSTREAM_REPO = "tailscale"
FORK_OWNER = "betdev-cloud"
FORK_REPO = "tailscale"
CHANGELOG_URL = "https://tailscale.com/changelog"
PRE_RELEASE_PATTERN = re.compile(r"-pre\d*$")
STABLE_TAG_PATTERN = re.compile(r"^v\d+\.\d+\.\d+$")


def github_session(token=None):
    session = requests.Session()
    session.headers.update(
        {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
    )
    auth_token = token or os.getenv("GITHUB_TOKEN")
    if auth_token:
        session.headers["Authorization"] = f"token {auth_token}"
    return session


def normalize_tag(version):
    version = version.strip()
    return version if version.startswith("v") else f"v{version}"


def parse_version(tag):
    return tuple(int(part) for part in normalize_tag(tag)[1:].split("."))


def compare_tags(left, right):
    left_parts = parse_version(left)
    right_parts = parse_version(right)
    length = max(len(left_parts), len(right_parts))
    left_parts += (0,) * (length - len(left_parts))
    right_parts += (0,) * (length - len(right_parts))
    if left_parts < right_parts:
        return -1
    if left_parts > right_parts:
        return 1
    return 0


def is_release_tag(tag_name):
    return STABLE_TAG_PATTERN.match(tag_name) is not None


def list_tags(owner, repo, session, limit=None):
    tags = []
    page = 1
    while True:
        response = session.get(
            f"https://api.github.com/repos/{owner}/{repo}/tags",
            params={"per_page": 100, "page": page},
        )
        response.raise_for_status()
        batch = response.json()
        if not batch:
            break
        tags.extend(batch)
        if limit and len(tags) >= limit:
            return tags[:limit]
        page += 1
    return tags


def get_tag_commit_sha(owner, repo, tag_name, session):
    response = session.get(
        f"https://api.github.com/repos/{owner}/{repo}/git/ref/tags/{tag_name}",
        headers=session.headers,
    )
    response.raise_for_status()
    object_data = response.json()["object"]
    if object_data["type"] == "commit":
        return object_data["sha"]

    tag_response = session.get(object_data["url"], headers=session.headers)
    tag_response.raise_for_status()
    return tag_response.json()["object"]["sha"]


def sorted_release_tags(tags):
    release_tags = [tag["name"] for tag in tags if is_release_tag(tag["name"])]
    return sorted(release_tags, key=cmp_to_key(compare_tags))


def previous_release_tag(tag_name, tags):
    release_tags = sorted_release_tags(tags)
    normalized = normalize_tag(tag_name)
    if normalized not in release_tags:
        return None
    index = release_tags.index(normalized)
    if index == 0:
        return None
    return release_tags[index - 1]


def get_latest_release_tag(owner, repo, session):
    """
    Return the latest published GitHub release tag name for the repository.
    """
    response = session.get(f"https://api.github.com/repos/{owner}/{repo}/releases/latest")
    response.raise_for_status()
    return response.json()["tag_name"]
