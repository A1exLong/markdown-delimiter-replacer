import tempfile
import unittest
from pathlib import Path

from replacer import (
    ReplaceOptions,
    ReplaceRule,
    process_file,
    process_folder,
    process_single_file,
    replace_text,
    prepare_rules,
)


class TextReplacementTests(unittest.TestCase):
    def test_default_inline_latex_both_delimiters(self):
        actual, count = replace_text(r'公式：\(x+1\)，结束。', ReplaceOptions())
        self.assertEqual((actual, count), ('公式：$x+1$，结束。', 2))

    def test_literal_regex_metacharacters_are_not_interpreted(self):
        opts = ReplaceOptions((ReplaceRule('[a-z]', '!'),))
        self.assertEqual(replace_text('A [a-z] bc', opts), ('A ! bc', 1))

    def test_sequential_rules(self):
        opts = ReplaceOptions((ReplaceRule('one', 'two'), ReplaceRule('two', '三')),)
        self.assertEqual(replace_text('one two', opts), ('三 三', 3))

    def test_regex_captures_and_multiline(self):
        opts = ReplaceOptions((ReplaceRule(r'(?m)^## (.+)$', r'<h2>\1</h2>', True),))
        self.assertEqual(replace_text('## A\n## B\n', opts), ('<h2>A</h2>\n<h2>B</h2>\n', 2))

    def test_regex_named_captures(self):
        opts = ReplaceOptions((ReplaceRule(r'(?P<a>\d+)', r'[\g<a>]', True),))
        self.assertEqual(replace_text('v12, v3', opts), ('v[12], v[3]', 2))

    def test_regex_multiline_explicit_dotall(self):
        opts = ReplaceOptions((ReplaceRule(r'(?s)\[\n(.*?)\n\]', r'$$\1$$', True),))
        self.assertEqual(replace_text('[\nx\ny\n]', opts), ('$$x\ny$$', 1))

    def test_blank_replacement_is_deletion(self):
        opts = ReplaceOptions((ReplaceRule('remove', ''),))
        self.assertEqual(replace_text('remove this remove', opts), (' this ', 2))

    def test_rule_errors_before_file_write(self):
        for opts in (
            ReplaceOptions(()),
            ReplaceOptions((ReplaceRule('', 'x'),)),
            ReplaceOptions((ReplaceRule('(', 'x', True),)),
            ReplaceOptions((ReplaceRule('(x)', r'\2', True),)),
        ):
            with self.subTest(opts=opts):
                with self.assertRaises(ValueError):
                    prepare_rules(opts)

    def test_untouched_file_does_not_create_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'note.md'
            path.write_text('not matched', encoding='utf-8')
            result = process_file(path, ReplaceOptions())
            self.assertTrue(result.skipped)
            self.assertFalse(Path(str(path) + '.bak').exists())

    def test_create_backup_and_not_overwrite_earlier_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'note.md'
            p.write_text('A', encoding='utf-8')
            r1 = process_file(p, ReplaceOptions((ReplaceRule('A', 'B'),), True))
            self.assertTrue(r1.changed)
            r2 = process_file(p, ReplaceOptions((ReplaceRule('B', 'C'),), True))
            self.assertTrue(r2.changed)
            self.assertEqual(p.read_text(encoding='utf-8'), 'C')
            self.assertEqual(Path(str(p) + '.bak').read_text(encoding='utf-8'), 'A')
            self.assertEqual(Path(str(p) + '.bak.1').read_text(encoding='utf-8'), 'B')

    def test_utf8_bom_and_crlf_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'note.txt'
            p.write_bytes(b'\xef\xbb\xbfa\r\nb\r\n')
            result = process_single_file(p, ReplaceOptions((ReplaceRule('a', 'c'),), False))
            self.assertEqual(result.changed_files, 1)
            self.assertEqual(p.read_bytes(), b'\xef\xbb\xbfc\r\nb\r\n')

    def test_gb18030_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'note.md'
            p.write_bytes('中文A'.encode('gb18030'))
            result = process_file(p, ReplaceOptions((ReplaceRule('A', 'B'),), False))
            self.assertTrue(result.changed)
            self.assertEqual(p.read_bytes(), '中文B'.encode('gb18030'))

    def test_invalid_unicode_replacement_does_not_modify_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'note.txt'
            source = '中文A'.encode('utf-8')
            p.write_bytes(source)
            # Unicode 代理码点无法编码成合法 UTF-8，应在写入/备份前拦截。
            result = process_file(p, ReplaceOptions((ReplaceRule('A', chr(0xD800)),), True))
            self.assertIsNotNone(result.error)
            self.assertEqual(p.read_bytes(), source)
            self.assertFalse(Path(str(p) + '.bak').exists())

    def test_folder_only_current_level_and_supported_extensions(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            for name in ('one.md', 'two.markdown', 'three.TXT', 'skip.csv'):
                (folder / name).write_text('ABC', encoding='utf-8')
            subfolder = folder / 'sub'
            subfolder.mkdir()
            (subfolder / 'nested.md').write_text('ABC', encoding='utf-8')
            options = ReplaceOptions((ReplaceRule('ABC', 'X'),), False)
            result = process_folder(folder, options)
            self.assertEqual((result.scanned_files, result.changed_files, result.total_replacements), (3, 3, 3))
            self.assertEqual((folder / 'skip.csv').read_text(encoding='utf-8'), 'ABC')
            self.assertEqual((subfolder / 'nested.md').read_text(encoding='utf-8'), 'ABC')

    def test_invalid_regex_keeps_all_files_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            p = folder / 'a.txt'
            p.write_text('abc', encoding='utf-8')
            with self.assertRaises(ValueError):
                process_folder(folder, ReplaceOptions((ReplaceRule('a', 'b'), ReplaceRule('(', 'x', True))))
            self.assertEqual(p.read_text(encoding='utf-8'), 'abc')

    def test_replace_same_text_skips_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'x.md'
            p.write_text('abc', encoding='utf-8')
            result = process_file(p, ReplaceOptions((ReplaceRule('abc', 'abc'),), True))
            self.assertTrue(result.skipped)
            self.assertFalse(Path(str(p) + '.bak').exists())


if __name__ == '__main__':
    unittest.main()
