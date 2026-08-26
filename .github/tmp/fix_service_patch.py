from pathlib import Path

path = Path('.github/tmp/patch_service_evidence.py')
text = path.read_text(encoding='utf-8')
old = """for path in ('docs/guides/webapp-product-walkthrough.md', 'translations/ja/docs/guides/webapp-product-walkthrough.md'):\n    p = ROOT / path\n    t = p.read_text(encoding='utf-8')\n    marker = '### CLI contract' if path.startswith('docs/') else '### CLI contract'\n    before = '\\n### CLI contract\\n'\n    if t.count(before) != 1:\n        raise SystemExit(f'{path}: CLI section marker changed')\n    if path.startswith('docs/'):\n"""
new = """for path in ('docs/guides/webapp-product-walkthrough.md', 'translations/ja/docs/guides/webapp-product-walkthrough.md'):\n    p = ROOT / path\n    t = p.read_text(encoding='utf-8')\n    before = '\\n### CLI contract\\n' if path.startswith('docs/') else '\\n`CLI_INTERFACE.md`:\\n'\n    if t.count(before) != 1:\n        raise SystemExit(f'{path}: CLI section marker changed')\n    if path.startswith('docs/'):\n"""
if text.count(old) != 1:
    raise SystemExit(f'expected service patch loop once, found {text.count(old)}')
path.write_text(text.replace(old, new), encoding='utf-8')
print('service patch marker fixed')
