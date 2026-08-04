from __future__ import annotations

import re
import unittest
from pathlib import Path
from typing import Any, Iterator

import yaml


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github/workflows"
FORBIDDEN_WORKFLOW_NAMES = frozenset({"pages.yml", "deploy-pages.yml"})
FORBIDDEN_ACTIONS = frozenset(
    {
        "actions/configure-pages",
        "actions/deploy-pages",
        "actions/upload-pages-artifact",
        "ad-m/github-push-action",
        "crazy-max/ghaction-github-pages",
        "jamesives/github-pages-deploy-action",
        "peaceiris/actions-gh-pages",
    }
)
SECRET_EXPRESSION = re.compile(
    r"\$\{\{(?:(?!\}\}).)*\bsecrets\s*(?:\.|\[)",
    re.IGNORECASE | re.DOTALL,
)
BRANCH_PUSH_COMMAND = re.compile(
    r"(?:^|[;&|]\s*|\n\s*)"
    r"(?:(?:command|exec)\s+)?"
    r"(?:env\b[^\n;&|]{0,160}?\s+)?"
    r"(?:(?:command|exec)\s+)?"
    r"(?:[^\s;&|]*/)?git\b[^\n;&|]{0,160}\bpush\b"
    r"|(?:^|[;&|]\s*|\n\s*)gh\s+api\b",
    re.IGNORECASE,
)


def load_workflow(path: Path) -> dict[str, Any]:
    workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(workflow, dict):
        raise AssertionError(f"{path}: workflow root must be a mapping")
    return workflow


def walk_yaml(
    value: Any, path: tuple[str, ...] = ()
) -> Iterator[tuple[tuple[str, ...], Any]]:
    yield path, value
    if isinstance(value, dict):
        for key, child in value.items():
            yield from walk_yaml(child, (*path, str(key)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk_yaml(child, (*path, f"[{index}]"))


def workflow_boundary_errors(workflow: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if "permissions" not in workflow:
        errors.append("workflow must declare explicit read-only permissions")

    for path, value in walk_yaml(workflow):
        key = path[-1].lower() if path else ""
        location = ".".join(path) or "<root>"

        if key == "uses" and isinstance(value, str):
            action = value.split("@", maxsplit=1)[0].lower()
            if action in FORBIDDEN_ACTIONS:
                errors.append(f"{location}: forbidden publishing action {action!r}")

        if key == "permissions":
            if isinstance(value, str) and value.lower() == "write-all":
                errors.append(f"{location}: write-all permission is forbidden")
            elif isinstance(value, dict):
                for permission, access in value.items():
                    if isinstance(access, str) and access.lower() == "write":
                        errors.append(
                            f"{location}.{permission}: write permission is forbidden"
                        )

        if key == "environment":
            environment_name: object = value
            if isinstance(value, dict):
                environment_name = value.get("name")
            if (
                isinstance(environment_name, str)
                and environment_name.lower() == "github-pages"
            ):
                errors.append(f"{location}: github-pages environment is forbidden")

        if key == "deploy" and value is True:
            errors.append(f"{location}: deploy=true is forbidden")

        if key == "secrets":
            errors.append(f"{location}: workflow secret access is forbidden")

        if isinstance(value, str):
            if SECRET_EXPRESSION.search(value):
                errors.append(f"{location}: secrets context is forbidden")
            if key in {"run", "script"} and BRANCH_PUSH_COMMAND.search(value):
                errors.append(f"{location}: repository push command is forbidden")

    return errors


class PagesDeploymentBoundaryTests(unittest.TestCase):
    def assert_rejected(self, source: str, expected: str) -> None:
        workflow = yaml.safe_load(source)
        self.assertIsInstance(workflow, dict)
        errors = workflow_boundary_errors(workflow)
        self.assertTrue(any(expected in error for error in errors), errors)

    def test_webapp_workflows_have_no_github_pages_deployment_route(self) -> None:
        workflow_files = sorted(
            path
            for path in WORKFLOWS.iterdir()
            if path.is_file() and path.suffix in {".yml", ".yaml"}
        )
        self.assertTrue(workflow_files, "expected a webapp validation workflow")
        self.assertFalse(FORBIDDEN_WORKFLOW_NAMES & {path.name for path in workflow_files})

        for workflow_file in workflow_files:
            with self.subTest(workflow=workflow_file.name):
                errors = workflow_boundary_errors(load_workflow(workflow_file))
                self.assertEqual([], errors)

    def test_rejects_quoted_pages_write_permission(self) -> None:
        self.assert_rejected(
            'permissions:\n  "pages": write\njobs: {}\n',
            "pages: write permission is forbidden",
        )

    def test_rejects_scalar_github_pages_environment(self) -> None:
        self.assert_rejected(
            "permissions:\n  contents: read\njobs:\n  deploy:\n"
            "    environment: github-pages\n",
            "github-pages environment is forbidden",
        )

    def test_rejects_branch_publication_capabilities(self) -> None:
        cases = {
            "contents write": (
                "permissions:\n  contents: write\njobs: {}\n",
                "contents: write permission is forbidden",
            ),
            "secret token": (
                "permissions:\n  contents: read\njobs:\n  publish:\n    steps:\n"
                '      - run: echo "${{ secrets.PAGES_TOKEN }}"\n',
                "secrets context is forbidden",
            ),
            "git push": (
                "permissions:\n  contents: read\njobs:\n  publish:\n    steps:\n"
                "      - run: git push origin gh-pages\n",
                "repository push command is forbidden",
            ),
        }
        for label, (source, expected) in cases.items():
            with self.subTest(label=label):
                self.assert_rejected(source, expected)

    def test_rejects_secret_expression_access_forms(self) -> None:
        expressions = (
            "${{ secrets.PAGES_TOKEN }}",
            "${{ secrets['PAGES_TOKEN'] }}",
            '${{ secrets [ "PAGES_TOKEN" ] }}',
            "${{ format('{0}', secrets.PAGES_TOKEN) }}",
        )
        for expression in expressions:
            with self.subTest(expression=expression):
                self.assert_rejected(
                    "permissions:\n  contents: read\njobs:\n  publish:\n    steps:\n"
                    f"      - env:\n          TOKEN: \"{expression}\"\n",
                    "secrets context is forbidden",
                )

    def test_rejects_wrapped_repository_push_commands(self) -> None:
        commands = (
            "/usr/bin/git push origin gh-pages",
            "command git push origin gh-pages",
            "env GIT_SSH_COMMAND=ssh git push origin gh-pages",
            "env GIT_SSH_COMMAND=ssh command git push origin gh-pages",
        )
        for command in commands:
            with self.subTest(command=command):
                self.assert_rejected(
                    "permissions:\n  contents: read\njobs:\n  publish:\n    steps:\n"
                    f"      - run: {command}\n",
                    "repository push command is forbidden",
                )


if __name__ == "__main__":
    unittest.main()
