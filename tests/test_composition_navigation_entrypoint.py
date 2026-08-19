from __future__ import annotations

import importlib
import unittest

from scripts import run_composition_navigation as runner


class CompositionNavigationEntrypointTests(unittest.TestCase):
    def test_viewers_patch_provider_order_in_helper_defining_modules(self) -> None:
        module_names = sorted(
            {
                name
                for names in runner.PATCH_MODULES.values()
                for name in names
            }
        )
        modules = {
            name: importlib.import_module(name)
            for name in module_names
        }
        original = {
            name: getattr(module, "PROVIDER_ORDER", None)
            for name, module in modules.items()
        }

        try:
            viewer = runner.load_command("viewer")
            self.assertEqual(viewer.PROVIDER_ORDER, runner.PROVIDER_ORDER)
            self.assertEqual(
                viewer.parse_providers.__globals__["PROVIDER_ORDER"],
                runner.PROVIDER_ORDER,
            )
            self.assertEqual(
                viewer.load_graph.__globals__["PROVIDER_ORDER"],
                runner.PROVIDER_ORDER,
            )

            locale_viewer = runner.load_command("locale-viewer")
            self.assertEqual(locale_viewer.PROVIDER_ORDER, runner.PROVIDER_ORDER)
            self.assertEqual(
                locale_viewer.parse_providers.__globals__["PROVIDER_ORDER"],
                runner.PROVIDER_ORDER,
            )
            self.assertEqual(
                locale_viewer.load_graph.__globals__["PROVIDER_ORDER"],
                runner.PROVIDER_ORDER,
            )
        finally:
            for name, value in original.items():
                module = modules[name]
                if value is None:
                    if hasattr(module, "PROVIDER_ORDER"):
                        delattr(module, "PROVIDER_ORDER")
                else:
                    module.PROVIDER_ORDER = value


if __name__ == "__main__":
    unittest.main()
