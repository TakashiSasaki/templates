from pathlib import Path

path = Path('.github/tmp/patch_pr507_followup.py')
text = path.read_text(encoding='utf-8')
old = 'generated `viewports/base` と `input-capability/keyboard` record では、positive / negative proof locator に `tests/test_task_ledger_browser.py`、proof kind に `end-to-end-test`、command ID に `verify-product` を使用します。expected result は file existence ではなく、対応する成功 interaction と rejected/absent invalid behavior を記述します。'
new = '生成された `viewports/base` と `input-capability/keyboard` recordでは、positive/negative proof locatorを `tests/test_task_ledger_browser.py`、proof kindを `end-to-end-test`、command IDを `verify-product` にします。expected resultには、単なるfileの存在ではなく、対応するsuccessful interactionと拒否または不在が確認されたinvalid behaviorを記述します。'
count = text.count(old)
if count != 2:
    raise SystemExit(f'expected 2 Japanese needle occurrences, found {count}')
path.write_text(text.replace(old, new), encoding='utf-8')
print('fixed Japanese needle in PR507 patch script')
