from pathlib import Path

prompt_path = Path("examples/evaluations/small-model-clean-room-field-log.txt")
prompt = prompt_path.read_text(encoding="utf-8")
old = "2. Before product coding, use the current implementation-evidence planning state to create a stable machine-readable requirement inventory. Keep commands, release gates, and implementation records empty at this stage; give each explicit caller-visible requirement its stable ID, description, empty recordIds, and requiredPositiveProofKinds. Preserve those IDs when later linking product records. Do not collapse unrelated requirements into one catch-all requirement."
new = "2. Before product coding, use the current implementation-evidence planning state to create a stable machine-readable requirement inventory. Keep commands, release gates, and implementation records empty at this stage; give each explicit caller-visible requirement its stable ID, description, non-empty contract target or targets, empty recordIds, and requiredPositiveProofKinds. Preserve those IDs and review the target mapping when later linking product records. Do not collapse unrelated requirements into one catch-all requirement."
if prompt.count(old) != 1:
    raise SystemExit(f"prompt guard failed: {prompt.count(old)}")
prompt_path.write_text(prompt.replace(old, new), encoding="utf-8")

catalog_path = Path("docs/publication-catalog.json")
catalog = catalog_path.read_text(encoding="utf-8")
old = '    {"id":"implementation-evidence-v4-migration","source":"components/lifecycle.implementation-evidence/files/docs/migrations/implementation-evidence-v3-to-v4.md","optional":false,"home":false},\n'
new = old + '    {"id":"implementation-evidence-v5-migration","source":"components/lifecycle.implementation-evidence/files/docs/migrations/implementation-evidence-v4-to-v5.md","optional":false,"home":false},\n'
if catalog.count(old) != 1:
    raise SystemExit(f"publication guard failed: {catalog.count(old)}")
catalog_path.write_text(catalog.replace(old, new), encoding="utf-8")
