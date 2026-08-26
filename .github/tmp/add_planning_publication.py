from pathlib import Path

path = Path("docs/publication-catalog.json")
text = path.read_text(encoding="utf-8")
needle = '    {"id":"implementation-evidence-v3-migration","source":"components/lifecycle.implementation-evidence/files/docs/migrations/implementation-evidence-v2-to-v3.md","optional":false,"home":false},\n'
addition = '    {"id":"implementation-evidence-v4-migration","source":"components/lifecycle.implementation-evidence/files/docs/migrations/implementation-evidence-v3-to-v4.md","optional":false,"home":false},\n'
if text.count(needle) != 1:
    raise SystemExit("implementation-evidence v3 migration publication entry changed")
if addition in text:
    raise SystemExit("implementation-evidence v4 migration is already published")
path.write_text(text.replace(needle, needle + addition), encoding="utf-8")
print("planning migration publication entry added")
