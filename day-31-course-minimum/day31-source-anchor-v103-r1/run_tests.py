import os,sys,unittest,gc,warnings
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
warnings.simplefilter('error',ResourceWarning)
resource_failures=[]
original_hook=sys.unraisablehook
def resource_hook(event):
    if isinstance(event.exc_value,ResourceWarning):resource_failures.append(str(event.exc_value))
    original_hook(event)
sys.unraisablehook=resource_hook
suite=unittest.defaultTestLoader.loadTestsFromNames(['test_runner','test_regression','test_prompt_profile','test_linked_blocks'])
result=unittest.TextTestRunner(verbosity=2).run(suite)
gc.collect()
sys.unraisablehook=original_hook
if resource_failures:raise SystemExit('Unraisable ResourceWarning: '+repr(resource_failures))
if result.skipped:raise SystemExit('Required checks skipped; no generation.')
raise SystemExit(0 if result.wasSuccessful() and result.testsRun==79 else 2)
