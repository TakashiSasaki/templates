from __future__ import annotations

import unittest

from scripts.check_mobile_layout import CASES


class MobileLayoutCompositionPathTests(unittest.TestCase):
    def test_webapp_template_uses_published_composition_destination(self) -> None:
        case = next(case for case in CASES if case.name == "webapp-template")
        self.assertEqual(case.path, "/webapp/TEMPLATE/")
        self.assertNotIn("/repository-trees/webapp/", case.path)

    def test_layout_cases_do_not_reference_retired_provider_tree_paths(self) -> None:
        for case in CASES:
            with self.subTest(case=case.name):
                self.assertNotIn("/repository-trees/skill/", case.path)
                self.assertNotIn("/repository-trees/webapp/", case.path)


if __name__ == "__main__":
    unittest.main()
