"""Open a known project folder and require its Explorer window to be foreground."""
import json
import os
from pathlib import Path
import subprocess
import sys


def open_folder(folder):
    if sys.platform != 'win32':
        command = 'open' if sys.platform == 'darwin' else 'xdg-open'
        try: subprocess.Popen([command, str(Path(folder).resolve())], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError as error: raise ValueError('Не удалось открыть папку в файловом менеджере.') from error
        return {'opened':True, 'foreground':None, 'confirmation':'Запуск файлового менеджера подтверждён; передний план отдельно не проверялся.'}
    powershell = Path(os.environ.get('WINDIR', r'C:\Windows'))/'System32/WindowsPowerShell/v1.0/powershell.exe'
    try:
        completed = subprocess.run(
            [str(powershell), '-NoProfile', '-NonInteractive', '-STA', '-WindowStyle', 'Hidden',
             '-File', str(Path(__file__).with_name('open_folder.ps1')), '-Folder', str(folder)],
            capture_output=True, text=True, encoding='utf-8', timeout=12,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), check=True)
        result = json.loads(completed.stdout.lstrip('\ufeff'))
    except (OSError, subprocess.SubprocessError, ValueError) as error:
        raise ValueError('Не удалось показать папку в Проводнике. Попробуйте открыть её ещё раз.') from error
    if (not isinstance(result, dict) or result.get('opened') is not True
            or result.get('foreground') is not True or not result.get('hwnd')
            or result.get('foreground_after') != result['hwnd']):
        raise ValueError('Папка открылась, но Проводник не вышел на передний план. Попробуйте ещё раз.')
    return result
