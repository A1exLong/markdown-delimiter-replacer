"""无需安装 Qt 的静态回归测试；附带可选的 Qt offscreen 真实控件测试。"""
import ast
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from config_manager import ConfigManager
from replacer import ReplaceRule

PROJECT = Path(__file__).resolve().parents[1]


class GuiStaticTests(unittest.TestCase):
    def test_gui_code_is_syntactically_valid(self):
        ast.parse((PROJECT / 'app.py').read_text(encoding='utf-8'))

    def test_GUI_features_and_open_default_program(self):
        source = (PROJECT / 'app.py').read_text(encoding='utf-8')
        for phrase in (
            'self.add_rule_button',
            'self._add_rule(',
            'self._remove_rule(',
            'self.rule_rows',
            'self.backup_checkbox',
            'self.open_after_process_checkbox',
            'QDesktopServices.openUrl',
            'regex_checkbox.isChecked()',
            'process_folder(',
            'process_single_file(',
        ):
            self.assertIn(phrase, source)

    def test_spec_and_build_script(self):
        spec = (PROJECT / 'MarkdownDelimiterReplacer.spec').read_text(encoding='utf-8')
        script = (PROJECT / 'scripts' / 'build_onefile.bat').read_text(encoding='utf-8')
        self.assertIn('console=False', spec)
        self.assertIn("name='MarkdownDelimiterReplacer'", spec)
        self.assertIn('MarkdownDelimiterReplacer.spec', script)


try:
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    from PySide6.QtWidgets import QApplication
    from app import MainWindow
except ImportError:
    QApplication = None
    MainWindow = None


@unittest.skipIf(QApplication is None, '当前 Python 环境未安装 PySide6，跳过真实 Qt 控件测试')
class QtWidgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_rule_creation_edit_deletion_and_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            # 不允许测试读取或污染真实用户配置。
            with patch('app.ConfigManager', return_value=ConfigManager(Path(tmp) / 'config.json')):
                window = MainWindow()
            try:
                self.assertGreaterEqual(len(window.rule_rows), 1)
                original_count = len(window.rule_rows)
                window._add_rule()
                self.assertEqual(len(window.rule_rows), original_count + 1)
                row = window.rule_rows[-1]
                row.source_edit.setText(r'\d+')
                row.replacement_edit.setText('X')
                row.regex_checkbox.setChecked(True)
                config = window._collect_config()
                self.assertEqual(config.rules[-1], ReplaceRule(r'\d+', 'X', True))
                window._remove_rule(row)
                self.assertEqual(len(window.rule_rows), original_count)
                window.folder_radio.setChecked(True)
                self.assertFalse(window.open_after_process_checkbox.isEnabled())
                window.file_radio.setChecked(True)
                self.assertTrue(window.open_after_process_checkbox.isEnabled())
            finally:
                window.close()


if __name__ == '__main__':
    unittest.main()
