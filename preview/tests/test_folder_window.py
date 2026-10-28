from pathlib import Path
import json, subprocess, sys, unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from folder_window import open_folder


class FolderWindowTests(unittest.TestCase):
    def run_result(self, result):
        return subprocess.CompletedProcess([], 0, json.dumps(result), '')

    def test_success_requires_the_requested_window_to_be_foreground(self):
        result={'opened':True,'foreground':True,'hwnd':42,'foreground_after':42}
        folder=Path("C:/Projects/Зоо кафе & $draft")
        with patch('folder_window.subprocess.run', return_value=self.run_result(result)) as run:
            self.assertEqual(open_folder(folder),result)
            args,options=run.call_args
            self.assertEqual(args[0][-2:],['-Folder',str(folder)])
            self.assertNotIn('-Command',args[0])
            self.assertNotIn('shell',options)
            self.assertEqual(options['timeout'],12)

    def test_background_or_wrong_window_is_not_success(self):
        for result in [
            {'opened':True,'foreground':False,'hwnd':42,'foreground_after':7},
            {'opened':True,'foreground':True,'hwnd':42,'foreground_after':7},
            {'opened':True,'foreground':True,'hwnd':0,'foreground_after':0},
            {'opened':False,'foreground':True,'hwnd':42,'foreground_after':42},
            []]:
            with self.subTest(result=result), patch('folder_window.subprocess.run', return_value=self.run_result(result)):
                with self.assertRaises(ValueError):open_folder(Path('C:/Projects/Game'))

    def test_helper_failures_do_not_report_opened(self):
        for error in [OSError('not found'),subprocess.TimeoutExpired('helper',12),subprocess.CalledProcessError(1,'helper')]:
            with self.subTest(error=error),patch('folder_window.subprocess.run',side_effect=error):
                with self.assertRaises(ValueError):open_folder(Path('C:/Projects/Game'))

    def test_invalid_output_does_not_report_opened(self):
        with patch('folder_window.subprocess.run',return_value=subprocess.CompletedProcess([],0,'not JSON','')):
            with self.assertRaises(ValueError):open_folder(Path('C:/Projects/Game'))
