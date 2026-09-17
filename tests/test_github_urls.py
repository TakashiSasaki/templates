import unittest

from site_renderer.github import (
    GitHubUrlError,
    github_blob_url,
    github_commit_url,
    github_tree_url,
    immutable_github_source_url,
)


REPOSITORY = "TakashiSasaki/templates"
REVISION = "a" * 40


class GitHubUrlTests(unittest.TestCase):
    def test_commit_blob_and_tree_urls_use_exact_revision(self):
        self.assertEqual(
            github_commit_url(REPOSITORY, REVISION),
            f"https://github.com/{REPOSITORY}/commit/{REVISION}",
        )
        self.assertEqual(
            github_blob_url(REPOSITORY, REVISION, "docs/index.md"),
            f"https://github.com/{REPOSITORY}/blob/{REVISION}/docs/index.md",
        )
        self.assertEqual(
            github_tree_url(REPOSITORY, REVISION, "docs"),
            f"https://github.com/{REPOSITORY}/tree/{REVISION}/docs",
        )

    def test_paths_and_fragments_are_encoded_without_losing_segments(self):
        path = "docs/space #?/%/日本語.md"
        self.assertEqual(
            github_blob_url(REPOSITORY, REVISION, path, fragment="heading one/β"),
            f"https://github.com/{REPOSITORY}/blob/{REVISION}/docs/space%20%23%3F/%25/%E6%97%A5%E6%9C%AC%E8%AA%9E.md#heading%20one/%CE%B2",
        )

    def test_non_commit_object_ids_and_moving_refs_are_rejected(self):
        for revision in ("integration", "b" * 39, "A" * 40, "g" * 40):
            with self.subTest(revision=revision), self.assertRaises(GitHubUrlError):
                github_commit_url(REPOSITORY, revision)

        for path in ("/absolute", "../escape", "docs//file.md"):
            with self.subTest(path=path), self.assertRaises(GitHubUrlError):
                github_blob_url(REPOSITORY, REVISION, path)

    def test_rewrites_only_known_authority_refs_and_preserves_kind_query_and_fragment(self):
        revisions = {"site": "a" * 40, "integration": "b" * 40, "composition": "c" * 40, "policy": "d" * 40}
        self.assertEqual(
            immutable_github_source_url(
                "https://github.com/TakashiSasaki/templates/blob/policy/README.md#development",
                revisions,
            ),
            "https://github.com/TakashiSasaki/templates/blob/" + "d" * 40 + "/README.md#development",
        )
        self.assertEqual(
            immutable_github_source_url(
                "https://github.com/TakashiSasaki/templates/tree/integration?plain=1",
                revisions,
            ),
            "https://github.com/TakashiSasaki/templates/tree/" + "b" * 40 + "?plain=1",
        )
        self.assertEqual(
            immutable_github_source_url(
                "https://github.com/TakashiSasaki/templates/blob/" + "e" * 40 + "/docs/a file.md",
                revisions,
            ),
            "https://github.com/TakashiSasaki/templates/blob/" + "e" * 40 + "/docs/a%20file.md",
        )
        external = "https://github.com/other/templates/blob/policy/README.md"
        self.assertEqual(immutable_github_source_url(external, revisions), external)
