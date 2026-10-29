"""Start the current catalogue; the previous interface remains in app/manager."""
from pathlib import Path
import runpy, sys
root = Path(__file__).resolve().parent
if (root/'.catalogue-installation.json').is_file() or (root/'.asemic-installation.json').is_file():
    from deployment import launch
    launch(root,open_browser='--no-browser' not in sys.argv)
    raise SystemExit(0)
sys.path.insert(0, str(root/'preview'))
if '--open' not in sys.argv:
    sys.argv.append('--open')
runpy.run_path(str(root/'preview/server.py'), run_name='__main__')
