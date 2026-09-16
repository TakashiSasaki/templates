"""Site preflight reaches the consumer suites and rejects provider escape hatches."""
from pathlib import Path
from unittest.mock import patch
import subprocess,sys,unittest
from scripts import run_site_preflight as preflight
ROOT=Path(__file__).resolve().parents[1]
class SitePreflightTests(unittest.TestCase):
 def test_provider_checkout_arguments_are_rejected(self):
  for argument in ('--composition-root','--policy-root','--staging-id'):
   result=subprocess.run([sys.executable,str(ROOT/'scripts/run_site_preflight.py'),'fast',argument,'x'],capture_output=True,text=True)
   self.assertEqual(result.returncode,2);self.assertIn('unrecognized arguments',result.stderr)
 def test_exact_head_guard_precedes_validation(self):
  with patch.object(sys,'argv',['preflight','fast','--expected-head','wrong']),patch.object(preflight.subprocess,'check_output',return_value='a'*40),patch.object(preflight.subprocess,'run') as run,self.assertRaises(SystemExit):preflight.main()
  run.assert_not_called()
 def test_full_profile_reaches_core_browser_and_bundle_reader(self):
  with patch.object(sys,'argv',['preflight','full','--bundle','bundle','--site-root','output']),patch.object(preflight.subprocess,'check_output',return_value='a'*40),patch.object(preflight.subprocess,'run') as run:preflight.main()
  commands=[call.args[0] for call in run.call_args_list]
  self.assertEqual([c[-1] for c in commands[:2]],['core','browser'])
  self.assertIn('scripts/check_bundle_reader.py',commands[2]);self.assertIn('--bundle',commands[2])
