import json
import tempfile
import unittest
from pathlib import Path

from config_manager import AppConfig, ConfigManager
from replacer import DEFAULT_RULES, ReplaceRule, ReplaceOptions, replace_text


class ConfigTests(unittest.TestCase):
    def test_defaults(self):
        c = AppConfig()
        self.assertEqual(tuple(c.rules), DEFAULT_RULES)
        self.assertTrue(c.create_backup)
        self.assertTrue(c.open_after_process)

    def test_round_trip_multirule_persistence(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'config.json'
            manager = ConfigManager(p)
            cfg = AppConfig(
                mode='folder',
                last_path='中文目录/demo',
                rules=[ReplaceRule(r'\(', '$'), ReplaceRule(r'(\d+)', r'num\1', True)],
                create_backup=False,
                open_after_process=False,
            )
            manager.save(cfg)
            actual = manager.load()
            self.assertEqual(actual, cfg)
            raw = json.loads(p.read_text(encoding='utf-8'))
            self.assertEqual(len(raw['rules']), 2)
            self.assertTrue(raw['rules'][1]['regex'])

    def test_migrate_v1_config_and_preserve_behavior(self):
        old = {
            'mode': 'file', 'last_path': '',
            'input_head': '[', 'input_tail': ']',
            'output_head': '$$', 'output_tail': '$$',
            'require_newline_after_head': True,
            'require_newline_before_tail': True,
            'ignore_case': False,
            'create_backup': False, 'open_after_process': True,
        }
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'config.json'
            p.write_text(json.dumps(old), encoding='utf-8')
            cfg = ConfigManager(p).load()
            self.assertEqual(len(cfg.rules), 1)
            self.assertTrue(cfg.rules[0].regex)
            result, count = replace_text('[\r\nHELLO\r\n] [inline]', ReplaceOptions(tuple(cfg.rules)))
            self.assertEqual((result, count), ('$$HELLO$$ [inline]', 1))
            self.assertFalse(cfg.create_backup)
            self.assertTrue(cfg.open_after_process)

    def test_corrupt_json_recovers_to_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'config.json'
            p.write_text('{not json', encoding='utf-8')
            c = ConfigManager(p).load()
            self.assertEqual(tuple(c.rules), DEFAULT_RULES)

    def test_invalid_regex_config_recovers_to_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'config.json'
            p.write_text(json.dumps({'rules': [{'source': '(', 'replacement': '', 'regex': True}]}), encoding='utf-8')
            c = ConfigManager(p).load()
            self.assertEqual(tuple(c.rules), DEFAULT_RULES)


if __name__ == '__main__':
    unittest.main()
