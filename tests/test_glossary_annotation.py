from __future__ import annotations

import unittest

from scripts.glossary_annotation import (
    GlossaryAnnotationError,
    build_annotation_index,
    find_annotation_matches,
)


def term(
    term_id: str,
    preferred: str,
    *,
    aliases: list[str] | None = None,
    japanese: tuple[str, list[str]] | None = None,
) -> dict[str, object]:
    value: dict[str, object] = {
        "id": term_id,
        "term": preferred,
        "aliases": aliases or [],
    }
    if japanese is not None:
        value["localized_labels"] = {
            "ja": {"term": japanese[0], "aliases": japanese[1]}
        }
    return value


class GlossaryAnnotationTests(unittest.TestCase):
    def test_all_glossary_label_forms_enter_the_derived_index(self) -> None:
        model = {
            "terms": [
                term(
                    "templates-publication-catalog",
                    "Publication catalog",
                    aliases=["Publication catalogue"],
                    japanese=("公開カタログ", ["パブリケーションカタログ"]),
                )
            ]
        }

        index = build_annotation_index(model)
        resolved = {label.normalized: label.term_id for label in index.labels}

        self.assertEqual(
            resolved["publication catalog"], "templates-publication-catalog"
        )
        self.assertEqual(
            resolved["publication catalogue"], "templates-publication-catalog"
        )
        self.assertEqual(resolved["公開カタログ"], "templates-publication-catalog")
        self.assertEqual(
            resolved["パブリケーションカタログ"], "templates-publication-catalog"
        )
        self.assertEqual(index.ambiguous, {})

    def test_future_glossary_term_requires_no_matching_code_change(self) -> None:
        model = {"terms": [term("templates-future-concept", "Future concept")]}

        matches = find_annotation_matches(
            "A Future concept can be added later.", build_annotation_index(model)
        )

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].term_id, "templates-future-concept")
        self.assertEqual("A Future concept can be added later."[matches[0].start:matches[0].end], "Future concept")

    def test_ambiguous_normalized_label_is_not_auto_resolved(self) -> None:
        model = {
            "terms": [
                term("templates-profile-one", "First profile", aliases=["Profile"]),
                term("templates-profile-two", "Second profile", aliases=["PROFILE"]),
            ]
        }

        index = build_annotation_index(model)

        self.assertEqual(
            index.ambiguous["profile"],
            ("templates-profile-one", "templates-profile-two"),
        )
        self.assertNotIn("profile", {label.normalized for label in index.labels})
        self.assertEqual(find_annotation_matches("Profile", index), [])

    def test_same_normalized_label_for_one_term_is_not_ambiguous(self) -> None:
        model = {
            "terms": [
                term("templates-profile", "Profile", aliases=["PROFILE"]),
            ]
        }

        index = build_annotation_index(model)

        self.assertEqual(index.ambiguous, {})
        self.assertEqual(find_annotation_matches("profile", index)[0].term_id, "templates-profile")

    def test_longest_match_wins_at_the_same_start_position(self) -> None:
        model = {
            "terms": [
                term("templates-publication", "Publication"),
                term("templates-publication-source-lock", "Publication source lock"),
            ]
        }
        text = "The Publication source lock is immutable."

        matches = find_annotation_matches(text, build_annotation_index(model))

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].term_id, "templates-publication-source-lock")
        self.assertEqual(text[matches[0].start:matches[0].end], "Publication source lock")

    def test_ascii_word_boundaries_prevent_identifier_substrings(self) -> None:
        model = {"terms": [term("external-git-branch", "Branch")]}
        text = "branch branching prebranch branch_name branch."

        matches = find_annotation_matches(text, build_annotation_index(model))

        self.assertEqual(
            [text[item.start:item.end] for item in matches],
            ["branch", "branch"],
        )

    def test_japanese_labels_do_not_require_whitespace_boundaries(self) -> None:
        model = {
            "terms": [
                term(
                    "templates-publication-catalog",
                    "Publication catalog",
                    japanese=("公開カタログ", []),
                )
            ]
        }
        text = "この公開カタログから入力を確認できます。"

        matches = find_annotation_matches(text, build_annotation_index(model))

        self.assertEqual(len(matches), 1)
        self.assertEqual(text[matches[0].start:matches[0].end], "公開カタログ")

    def test_casefold_and_decomposed_unicode_preserve_source_span(self) -> None:
        model = {"terms": [term("templates-cafe", "CAFÉ")]}
        text = "Cafe\u0301 guidance"

        matches = find_annotation_matches(text, build_annotation_index(model))

        self.assertEqual(len(matches), 1)
        self.assertEqual(text[matches[0].start:matches[0].end], "Cafe\u0301")

    def test_invalid_integrated_model_fails_closed(self) -> None:
        with self.assertRaisesRegex(GlossaryAnnotationError, "must contain terms"):
            build_annotation_index({})


if __name__ == "__main__":
    unittest.main()
