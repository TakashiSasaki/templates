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

DEFAULT_PROTECTED_BRANCHES = frozenset({"main", "bootstrap-agent-policy"})
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
        payload: dict[str, Any] | None = None,
    ) -> tuple[Any, dict[str, str]]:
        url = f"{self.api_url}{path}"
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(
            url,
            data=data,
            method=method,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.token}",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "agent-policy-repository-hygiene",
            },
        )
        try:
            with urllib.request.urlopen(request) as response:
                raw = response.read()
                body = json.loads(raw) if raw else None
                headers = {key.lower(): value for key, value in response.headers.items()}
                return body, headers
        except urllib.error.HTTPError as error:
            details = error.read().decode("utf-8", errors="replace")
            raise MaintenanceError(
                f"GitHub API {method} {path} failed with HTTP {error.code}: {details}"
            ) from error

    def get_all(self, path: str) -> list[dict[str, Any]]:
        separator = "&" if "?" in path else "?"
        page = 1
        values: list[dict[str, Any]] = []
        while True:
            body, _ = self.request("GET", f"{path}{separator}per_page=100&page={page}")
            if not isinstance(body, list):
                raise MaintenanceError(f"Expected list response from {path}")
            values.extend(body)
            if len(body) < 100:
                return values
            page += 1

    def repository_metadata(self) -> dict[str, Any]:
        body, _ = self.request("GET", f"/repos/{self.repository}")
        if not isinstance(body, dict):
            raise MaintenanceError("Expected repository metadata object")
        return body

    def open_pull_requests(self) -> list[PullRequest]:
        values = self.get_all(f"/repos/{self.repository}/pulls?state=open")
        return [PullRequest.from_api(value) for value in values]

    def branches(self) -> list[dict[str, Any]]:
        return self.get_all(f"/repos/{self.repository}/branches")

    def pulls_for_commit(self, sha: str) -> list[PullRequest]:
        values = self.get_all(f"/repos/{self.repository}/commits/{sha}/pulls")
        return [PullRequest.from_api(value) for value in values]

    def comment(self, number: int, body: str) -> None:
        self.request(
            "POST",
            f"/repos/{self.repository}/issues/{number}/comments",
            {"body": body},
        )

    def close_pull_request(self, number: int) -> None:
        self.request(
            "PATCH",
            f"/repos/{self.repository}/pulls/{number}",
            {"state": "closed"},
        )

    def delete_branch(self, branch: str) -> None:
        encoded = urllib.parse.quote(branch, safe="/")
        self.request("DELETE", f"/repos/{self.repository}/git/refs/heads/{encoded}")


def run_git(*arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *arguments],
        check=check,
        capture_output=True,
        text=True,
    )


def fetch_pull_request(pr: PullRequest) -> None:
    run_git(
        "fetch",
        "--no-tags",
        "origin",
        f"+refs/heads/{pr.base.branch}:refs/remotes/origin/{pr.base.branch}",
        f"+refs/pull/{pr.number}/head:refs/remotes/pull/{pr.number}/head",
    )


def commit_tree(sha: str) -> str:
    return run_git("show", "-s", "--format=%T", sha).stdout.strip()


def merge_result_tree(base_sha: str, head_sha: str) -> str | None:
    result = run_git("merge-tree", "--write-tree", base_sha, head_sha, check=False)
    if result.returncode != 0:
        return None
    first_line = result.stdout.splitlines()[0] if result.stdout else ""
    return first_line.strip() or None


def pull_request_is_noop(pr: PullRequest, repository: str) -> bool:
    if pr.head.repository != repository:
        return False
    fetch_pull_request(pr)
    merged_tree = merge_result_tree(pr.base.sha, pr.head.sha)
    return merged_tree is not None and merged_tree == commit_tree(pr.base.sha)


def merged_pr_matches_branch(
    pr: PullRequest,
    repository: str,
    branch: str,
    sha: str,
) -> bool:
    return (
        pr.merged_at is not None
        and pr.head.repository == repository
        and pr.head.branch == branch
        and pr.head.sha == sha
    )


def close_noop_pull_requests(
    api: GitHubApi,
    repository: str,
    protected_branches: set[str],
    apply: bool,
) -> tuple[list[PullRequest], set[str]]:
    open_prs = api.open_pull_requests()
    closed_branches: set[str] = set()
    for pr in open_prs:
        if pr.head.branch in protected_branches:
            print(f"Skipping PR #{pr.number}: protected head branch {pr.head.branch}.")
            continue
        if not pull_request_is_noop(pr, repository):
            print(f"PR #{pr.number} changes the merge result; leaving it open.")
            continue

        print(
            f"PR #{pr.number} is redundant: merging `{pr.head.branch}` into "
            f"`{pr.base.branch}` produces the same Git tree as the base branch."
        )
        if apply:
            api.comment(
                pr.number,
                (
                    f"{COMMENT_MARKER}\n"
                    "This pull request was closed automatically because its merge result "
                    "would not change the base branch. This commonly occurs when a branch "
                    "remains after a squash merge."
                ),
            )
            api.close_pull_request(pr.number)
        closed_branches.add(pr.head.branch)

    remaining = [
        pr for pr in open_prs if pr.head.branch not in closed_branches or not apply
    ]
    return remaining, closed_branches


def delete_merged_branches(
    api: GitHubApi,
    repository: str,
    default_branch: str,
    protected_branches: set[str],
    open_prs: list[PullRequest],
    apply: bool,
) -> list[str]:
    open_heads = {
        pr.head.branch for pr in open_prs if pr.head.repository == repository
    }
    deleted: list[str] = []
    for branch in api.branches():
        name = str(branch["name"])
        sha = str(branch["commit"]["sha"])

        if name == default_branch or name in protected_branches:
            print(f"Keeping protected branch {name}.")
            continue
        if bool(branch.get("protected")):
            print(f"Keeping GitHub-protected branch {name}.")
            continue
        if name in open_heads:
            print(f"Keeping branch {name}: it is used by an open pull request.")
            continue

        pulls = api.pulls_for_commit(sha)
        if not any(merged_pr_matches_branch(pr, repository, name, sha) for pr in pulls):
            print(f"Keeping branch {name}: no matching merged pull request at its tip.")
            continue

        print(f"Deleting merged branch {name} at {sha}.")
        if apply:
            api.delete_branch(name)
        deleted.append(name)
    return deleted


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Close no-op pull requests and delete safely merged branches."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes. The default is a dry run.",
    )
    parser.add_argument(
        "--repository",
        default=os.environ.get("GITHUB_REPOSITORY"),
        help="Repository in owner/name form.",
    )
    parser.add_argument(
        "--api-url",
        default=os.environ.get("GITHUB_API_URL", "https://api.github.com"),
    )
    parser.add_argument(
        "--protect",
        action="append",
        default=[],
        metavar="BRANCH",
        help="Additional branch to protect from closure and deletion.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    token = os.environ.get("GITHUB_TOKEN", "")
    if not args.repository:
        print("--repository or GITHUB_REPOSITORY is required.", file=sys.stderr)
        return 2
    if not token:
        print("GITHUB_TOKEN is required.", file=sys.stderr)
        return 2

    protected = set(DEFAULT_PROTECTED_BRANCHES)
    protected.update(args.protect)

    api = GitHubApi(args.api_url, args.repository, token)
    metadata = api.repository_metadata()
    default_branch = str(metadata["default_branch"])
    protected.add(default_branch)

    mode = "APPLY" if args.apply else "DRY RUN"
    print(f"Repository hygiene mode: {mode}")
    print(f"Protected branches: {', '.join(sorted(protected))}")

    open_prs, _ = close_noop_pull_requests(
        api,
        args.repository,
        protected,
        args.apply,
    )
    delete_merged_branches(
        api,
        args.repository,
        default_branch,
        protected,
        open_prs,
        args.apply,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
