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
        text = "A Future concept can be added later."

        matches = find_annotation_matches(text, build_annotation_index(model))

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].term_id, "templates-future-concept")
        self.assertEqual(text[matches[0].start:matches[0].end], "Future concept")

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
        self.assertEqual(
            find_annotation_matches("profile", index)[0].term_id,
            "templates-profile",
        )

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
        self.assertEqual(
            text[matches[0].start:matches[0].end],
            "Publication source lock",
        )

    def test_ascii_word_boundaries_prevent_identifier_substrings(self) -> None:
        model = {"terms": [term("external-git-branch", "Branch")]}
        text = "branch branching prebranch branch_name branch."

        matches = find_annotation_matches(text, build_annotation_index(model))

        self.assertEqual(
            [text[item.start:item.end] for item in matches],
            ["branch", "branch"],
        )

    def test_punctuation_labels_enforce_each_ascii_boundary_independently(self) -> None:
        left_model = {
            "terms": [term("templates-branch-bang", "Branch!")]
        }
        left_text = "subbranch! branch!"
        left_matches = find_annotation_matches(
            left_text,
            build_annotation_index(left_model),
        )
        self.assertEqual(
            [left_text[item.start:item.end] for item in left_matches],
            ["branch!"],
        )

        right_model = {
            "terms": [term("templates-at-branch", "@branch")]
        }
        right_text = "@branching @branch"
        right_matches = find_annotation_matches(
            right_text,
            build_annotation_index(right_model),
        )
        self.assertEqual(
            [right_text[item.start:item.end] for item in right_matches],
            ["@branch"],
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

    def test_canceling_unicode_expansion_and_contraction_preserve_offsets(self) -> None:
        model = {
            "terms": [
                term("templates-double-s", "SS"),
                term("templates-cafe", "CAFÉ"),
            ]
        }
        text = "ß Cafe\u0301"

        matches = find_annotation_matches(text, build_annotation_index(model))

        self.assertEqual(
            [(item.term_id, text[item.start:item.end]) for item in matches],
            [
                ("templates-double-s", "ß"),
                ("templates-cafe", "Cafe\u0301"),
            ],
        )

    def test_decomposed_hangul_preserves_normalized_source_span(self) -> None:
        model = {"terms": [term("templates-hangul", "각")]}
        text = "각 확인"

        matches = find_annotation_matches(text, build_annotation_index(model))

        self.assertEqual(len(matches), 1)
        self.assertEqual(text[matches[0].start:matches[0].end], "각")

    def test_invalid_integrated_model_fails_closed(self) -> None:
        with self.assertRaisesRegex(GlossaryAnnotationError, "must contain terms"):
            build_annotation_index({})

    def test_invalid_localized_labels_type_fails_closed(self) -> None:
        malformed = term("templates-invalid", "Invalid")
        malformed["localized_labels"] = ["ja"]

        with self.assertRaisesRegex(
            GlossaryAnnotationError,
            "localized_labels must be an object",
        ):
            build_annotation_index({"terms": [malformed]})

    def test_invalid_alias_type_fails_closed(self) -> None:
        malformed = term("templates-invalid", "Invalid")
        malformed["aliases"] = "Alias"

        with self.assertRaisesRegex(
            GlossaryAnnotationError,
            "aliases must be an array",
        ):
            build_annotation_index({"terms": [malformed]})


if __name__ == "__main__":
    unittest.main()
