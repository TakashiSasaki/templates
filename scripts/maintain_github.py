#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

DEFAULT_PROTECTED_BRANCHES = frozenset({"site", "webapp", "policy", "skill"})
COMMENT_MARKER = "<!-- agent-policy-repository-hygiene -->"


class MaintenanceError(RuntimeError):
    pass


@dataclass(frozen=True)
class PullRequestRef:
    repository: str
    branch: str
    sha: str


@dataclass(frozen=True)
class PullRequest:
    number: int
    title: str
    base: PullRequestRef
    head: PullRequestRef
    merged_at: str | None

    @classmethod
    def from_api(cls, value: dict[str, Any]) -> PullRequest:
        return cls(
            number=int(value["number"]),
            title=str(value["title"]),
            base=_ref_from_api(value["base"]),
            head=_ref_from_api(value["head"]),
            merged_at=value.get("merged_at"),
        )


def _ref_from_api(value: dict[str, Any]) -> PullRequestRef:
    repository = value.get("repo")
    full_name = repository.get("full_name") if repository else ""
    return PullRequestRef(
        repository=str(full_name or ""),
        branch=str(value["ref"]),
        sha=str(value["sha"]),
    )


class GitHubApi:
    def __init__(self, api_url: str, repository: str, token: str) -> None:
        self.api_url = api_url.rstrip("/")
        self.repository = repository
        self.token = token

    def request(
        self,
        method: str,
        path: str,
        *,
        query: dict[str, str] | None = None,
        body: object | None = None,
    ) -> object:
        url = f"{self.api_url}/repos/{self.repository}{path}"
        if query:
            url = f"{url}?{urllib.parse.urlencode(query)}"
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
        request = urllib.request.Request(  # noqa: S310
            url,
            data=data,
            method=method,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.token}",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "agent-policy-repository-maintenance",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
                content = response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise MaintenanceError(
                f"GitHub API {method} {path} failed with {exc.code}: {detail}"
            ) from exc
        if not content:
            return None
        return json.loads(content.decode("utf-8"))


def git(*arguments: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", *arguments],
        check=check,
        text=True,
        capture_output=True,
    )
    return result.stdout.strip()


def repository_full_name() -> str:
    value = os.environ.get("GITHUB_REPOSITORY")
    if value:
        return value
    remote = git("remote", "get-url", "origin")
    match = urllib.parse.urlparse(remote)
    if match.scheme in {"http", "https", "ssh"}:
        path = match.path
    elif remote.startswith("git@") and ":" in remote:
        path = remote.split(":", 1)[1]
    else:
        path = remote
    path = path.removesuffix(".git").strip("/")
    if "/" not in path:
        raise MaintenanceError(f"Cannot derive repository name from origin: {remote}")
    return path


def default_branch(api: GitHubApi) -> str:
    value = api.request("GET", "")
    if not isinstance(value, dict) or not isinstance(value.get("default_branch"), str):
        raise MaintenanceError("Repository response did not include default_branch")
    return value["default_branch"]


def branch_exists(api: GitHubApi, branch: str) -> bool:
    encoded = urllib.parse.quote(branch, safe="")
    try:
        api.request("GET", f"/branches/{encoded}")
    except MaintenanceError as exc:
        if "failed with 404" in str(exc):
            return False
        raise
    return True


def local_branch_exists(branch: str) -> bool:
    result = subprocess.run(
        ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"],
        check=False,
    )
    return result.returncode == 0


def remote_branch_exists(branch: str) -> bool:
    result = subprocess.run(
        ["git", "show-ref", "--verify", "--quiet", f"refs/remotes/origin/{branch}"],
        check=False,
    )
    return result.returncode == 0


def branch_merged_into(branch: str, target: str) -> bool:
    branch_ref = f"refs/remotes/origin/{branch}"
    target_ref = f"refs/remotes/origin/{target}"
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", branch_ref, target_ref],
        check=False,
    )
    return result.returncode == 0


def open_pull_requests(api: GitHubApi) -> tuple[PullRequest, ...]:
    value = api.request("GET", "/pulls", query={"state": "open", "per_page": "100"})
    if not isinstance(value, list):
        raise MaintenanceError("Pull-request response was not a list")
    return tuple(PullRequest.from_api(item) for item in value if isinstance(item, dict))


def merged_pull_requests(api: GitHubApi) -> tuple[PullRequest, ...]:
    value = api.request(
        "GET",
        "/pulls",
        query={"state": "closed", "sort": "updated", "direction": "desc", "per_page": "100"},
    )
    if not isinstance(value, list):
        raise MaintenanceError("Pull-request response was not a list")
    return tuple(
        pull_request
        for item in value
        if isinstance(item, dict)
        for pull_request in (PullRequest.from_api(item),)
        if pull_request.merged_at is not None
    )


def branches(api: GitHubApi) -> tuple[str, ...]:
    value = api.request("GET", "/branches", query={"per_page": "100"})
    if not isinstance(value, list):
        raise MaintenanceError("Branch response was not a list")
    result: list[str] = []
    for item in value:
        if isinstance(item, dict) and isinstance(item.get("name"), str):
            result.append(item["name"])
    return tuple(result)


def comment_body(branch: str, pull_request: int) -> str:
    return (
        f"{COMMENT_MARKER}\n"
        f"Branch `{branch}` appears to be merged by PR #{pull_request} and is eligible "
        "for deletion after confirming that it is no longer needed."
    )


def existing_comment_ids(api: GitHubApi, issue_number: int) -> tuple[int, ...]:
    value = api.request(
        "GET",
        f"/issues/{issue_number}/comments",
        query={"per_page": "100"},
    )
    if not isinstance(value, list):
        raise MaintenanceError("Issue-comment response was not a list")
    result: list[int] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        if COMMENT_MARKER in str(item.get("body", "")):
            identifier = item.get("id")
            if isinstance(identifier, int):
                result.append(identifier)
    return tuple(result)


def add_comment(api: GitHubApi, issue_number: int, body: str) -> None:
    api.request("POST", f"/issues/{issue_number}/comments", body={"body": body})


def merged_pr_for_branch(
    merged: tuple[PullRequest, ...], repository: str, branch: str
) -> PullRequest | None:
    for pull_request in merged:
        if (
            pull_request.head.repository == repository
            and pull_request.head.branch == branch
        ):
            return pull_request
    return None


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Identify and optionally delete merged feature branches."
    )
    parser.add_argument(
        "--delete",
        action="store_true",
        help="Delete eligible remote and local feature branches.",
    )
    parser.add_argument(
        "--comment",
        action="store_true",
        help="Leave an idempotent cleanup reminder on the merged pull request.",
    )
    parser.add_argument(
        "--protected-branch",
        action="append",
        default=[],
        help="Additional branch name that must never be deleted.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("GITHUB_TOKEN is required", file=sys.stderr)
        return 2
    repository = repository_full_name()
    api = GitHubApi(
        os.environ.get("GITHUB_API_URL", "https://api.github.com"),
        repository,
        token,
    )
    default = default_branch(api)
    protected = set(DEFAULT_PROTECTED_BRANCHES)
    protected.add(default)
    protected.update(args.protected_branch)

    git("fetch", "--prune", "origin")
    open_prs = open_pull_requests(api)
    merged_prs = merged_pull_requests(api)
    open_heads = {
        pull_request.head.branch
        for pull_request in open_prs
        if pull_request.head.repository == repository
    }

    removed_any = False
    for branch in branches(api):
        if branch in protected or branch in open_heads:
            continue
        merged_pr = merged_pr_for_branch(merged_prs, repository, branch)
        if merged_pr is None or not remote_branch_exists(branch):
            continue
        if not branch_merged_into(branch, default):
            continue

        if args.comment and not existing_comment_ids(api, merged_pr.number):
            add_comment(api, merged_pr.number, comment_body(branch, merged_pr.number))
            print(f"commented on PR #{merged_pr.number} for branch {branch}")

        if not args.delete:
            print(f"eligible: {branch} (PR #{merged_pr.number})")
            continue

        encoded = urllib.parse.quote(branch, safe="")
        api.request("DELETE", f"/git/refs/heads/{encoded}")
        if local_branch_exists(branch):
            git("branch", "-D", branch)
        print(f"deleted: {branch} (PR #{merged_pr.number})")
        removed_any = True

    return 0 if removed_any or not args.delete else 0


if __name__ == "__main__":
    raise SystemExit(main())
