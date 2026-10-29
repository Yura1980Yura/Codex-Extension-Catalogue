"""Resolve the target user's Codex profile without borrowing another user's state."""
import os
from pathlib import Path


def codex_dir(home=None):
    home = Path(home or Path.home()).expanduser().resolve()
    override = os.environ.get("CODEX_HOME") if home == Path.home().resolve() else None
    return Path(override).expanduser().resolve() if override else home/".codex"


def user_folder(kind, home=None):
    home = Path(home or Path.home()).resolve()
    if os.name == "nt" and home == Path.home().resolve():
        # Handles redirected Desktop/Documents, including OneDrive.
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                    r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders") as key:
                value = winreg.QueryValueEx(key, "Desktop" if kind == "Desktop" else "Personal")[0]
                return Path(os.path.expandvars(value))
        except OSError:
            pass
    if os.name != "nt":
        config = Path(os.environ.get("XDG_CONFIG_HOME", str(home/".config")))/"user-dirs.dirs"
        try:
            import re
            text = config.read_text(encoding="utf-8")
            match = re.search(r'^XDG_'+kind.upper()+r'_DIR="([^"\n]+)"$', text, re.M)
            if match:
                value = match[1].replace("$HOME", str(home))
                if "$" not in value and Path(value).is_absolute(): return Path(value)
        except OSError:
            pass
    return home/kind
