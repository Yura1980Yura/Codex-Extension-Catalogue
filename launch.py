"""Start the current catalogue; the previous interface remains in app/manager."""
from pathlib import Path
import runpy, sys
root = Path(__file__).resolve().parent
sys.path.insert(0, str(root/'preview'))
if '--open' not in sys.argv:
    sys.argv.append('--open')
runpy.run_path(str(root/'preview/server.py'), run_name='__main__')
