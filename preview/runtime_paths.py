"""Share profile resolution with the standalone catalogue skill."""
from pathlib import Path
import sys
root = Path(__file__).resolve().parents[1]
scripts = root/"app/skill-catalog/scripts"
if not scripts.is_dir(): scripts = root/"skill-catalog/scripts"
sys.path.insert(0, str(scripts))
from platform_paths import codex_dir
