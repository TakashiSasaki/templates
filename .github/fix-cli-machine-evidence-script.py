from pathlib import Path

path = Path('.github/tmp-cli-machine-evidence.py')
text = path.read_text(encoding='utf-8')

old = """needle = textwrap.dedent(
    '''\\
            self.assertEqual(
                dependency_closure(\"artifact.skill-core\", \"lifecycle.release-bundle\"),
    '''
)
insertion = textwrap.dedent(
    '''\\
            self.assertEqual(
                dependency_closure(\"artifact.skill-core\", \"capability.cli\"),
                {
                    \"artifact.skill-core\",
                    \"capability.cli\",
                    \"capability.runtime\",
                    \"lifecycle.composition-state\",
                    \"lifecycle.contract-evolution\",
                    \"lifecycle.implementation-evidence\",
                },
            )

    '''
)
"""
new = """needle = (
    '        self.assertEqual(\\n'
    '            dependency_closure(\"artifact.skill-core\", \"lifecycle.release-bundle\"),\\n'
)
insertion = (
    '        self.assertEqual(\\n'
    '            dependency_closure(\"artifact.skill-core\", \"capability.cli\"),\\n'
    '            {\\n'
    '                \"artifact.skill-core\",\\n'
    '                \"capability.cli\",\\n'
    '                \"capability.runtime\",\\n'
    '                \"lifecycle.composition-state\",\\n'
    '                \"lifecycle.contract-evolution\",\\n'
    '                \"lifecycle.implementation-evidence\",\\n'
    '            },\\n'
    '        )\\n\\n'
)
"""
if text.count(old) != 1:
    raise SystemExit(f'catalog block occurrence count: {text.count(old)}')
text = text.replace(old, new)

old_start = "method = textwrap.dedent(\n    r'''\n"
new_start = "method = textwrap.indent(\n    textwrap.dedent(\n        r'''\n"
if text.count(old_start) != 1:
    raise SystemExit(f'method start occurrence count: {text.count(old_start)}')
text = text.replace(old_start, new_start)

old_end = "                self.assertEqual(cli_contract[\"entrypoints\"], [])\n    '''\n)\nif text.count(marker) != 1:\n"
new_end = "                self.assertEqual(cli_contract[\"entrypoints\"], [])\n        '''\n    ),\n    \"    \",\n)\nif text.count(marker) != 1:\n"
if text.count(old_end) != 1:
    raise SystemExit(f'method end occurrence count: {text.count(old_end)}')
text = text.replace(old_end, new_end)

path.write_text(text, encoding='utf-8')
