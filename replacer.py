"""文本逐条替换引擎：不依赖 Qt，方便独立测试。"""
from __future__ import annotations

import os
import re
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

SUPPORTED_EXTENSIONS = frozenset({".md", ".markdown", ".txt"})


@dataclass(frozen=True)
class ReplaceRule:
    """一个完整替换规则。regex=False 时严格按字面文本替换。"""
    source: str
    replacement: str
    regex: bool = False


DEFAULT_RULES: tuple[ReplaceRule, ...] = (
    ReplaceRule(source=r"\(", replacement="$"),
    ReplaceRule(source=r"\)", replacement="$"),
)


@dataclass(frozen=True)
class ReplaceOptions:
    rules: tuple[ReplaceRule, ...] = DEFAULT_RULES
    create_backup: bool = True


@dataclass(frozen=True)
class PreparedRule:
    source: str
    replacement: str
    pattern: re.Pattern[str] | None  # None: 字面替换


@dataclass
class FileResult:
    path: Path
    replacements: int = 0
    changed: bool = False
    skipped: bool = False
    error: str | None = None


@dataclass
class BatchResult:
    scanned_files: int = 0
    changed_files: int = 0
    skipped_files: int = 0
    total_replacements: int = 0
    changed_paths: list[Path] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def prepare_rules(options: ReplaceOptions) -> tuple[PreparedRule, ...]:
    """处理任何文件前，统一校验所有规则（含正则和捕获组引用）。"""
    if not options.rules:
        raise ValueError("请至少添加一条替换规则。")

    prepared: list[PreparedRule] = []
    for index, rule in enumerate(options.rules, start=1):
        if not isinstance(rule, ReplaceRule):
            raise TypeError(f"第 {index} 条规则的类型错误。")
        if not isinstance(rule.source, str) or not rule.source:
            raise ValueError(f"第 {index} 条规则：原文本不能为空。")
        if not isinstance(rule.replacement, str):
            raise ValueError(f"第 {index} 条规则：替换文本必须是字符串。")
        if type(rule.regex) is not bool:
            raise ValueError(f"第 {index} 条规则：正则开关必须是布尔值。")

        if rule.regex:
            try:
                compiled = re.compile(rule.source)
                # 即使输入无匹配，也会预先校验 \1、\g<name> 等替换引用。
                compiled.sub(rule.replacement, "")
            except (re.error, IndexError, ValueError) as exc:
                raise ValueError(f"第 {index} 条规则的正则表达式无效：{exc}") from exc
        else:
            compiled = None

        prepared.append(PreparedRule(rule.source, rule.replacement, compiled))

    return tuple(prepared)


def replace_text(
    text: str,
    options: ReplaceOptions,
    prepared: tuple[PreparedRule, ...] | None = None,
) -> tuple[str, int]:
    """依序执行规则：后续规则处理前一条规则的输出。"""
    if prepared is None:
        prepared = prepare_rules(options)

    count_total = 0
    result = text
    for rule in prepared:
        if rule.pattern is None:
            count = result.count(rule.source)
            if count:
                result = result.replace(rule.source, rule.replacement)
        else:
            result, count = rule.pattern.subn(rule.replacement, result)
        count_total += count
    return result, count_total


def detect_encoding(raw: bytes) -> str:
    if raw.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    for encoding in ("utf-8", "gb18030"):
        try:
            raw.decode(encoding)
            return encoding
        except UnicodeDecodeError:
            continue
    raise UnicodeError("编码无法识别：当前支持 UTF-8、UTF-8 BOM、GB18030。")


def read_text_preserve_encoding(path: Path) -> tuple[str, str]:
    raw = path.read_bytes()
    encoding = detect_encoding(raw)
    return raw.decode(encoding), encoding


def next_backup_path(path: Path) -> Path:
    base = path.with_name(f"{path.name}.bak")
    if not base.exists():
        return base
    number = 1
    while True:
        candidate = path.with_name(f"{path.name}.bak.{number}")
        if not candidate.exists():
            return candidate
        number += 1


def atomic_write_text(path: Path, text: str, encoding: str) -> None:
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    tmp = Path(temp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(text.encode(encoding))
            handle.flush()
            os.fsync(handle.fileno())
        try:
            shutil.copystat(path, tmp)
        except OSError:
            pass
        os.replace(tmp, path)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


def validate_target_file(path: Path) -> None:
    if not path.is_file():
        if not path.exists():
            raise FileNotFoundError(f"文件不存在：{path}")
        raise ValueError(f"目标不是普通文件：{path}")
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError("只支持 .md / .markdown / .txt 文件。")


def _process_file(path: Path, options: ReplaceOptions, prepared: tuple[PreparedRule, ...]) -> FileResult:
    path = path.expanduser().resolve()
    try:
        validate_target_file(path)
        source, encoding = read_text_preserve_encoding(path)
        output, count = replace_text(source, options, prepared)
        if output == source:
            return FileResult(path=path, skipped=True)
        # 在创建备份/写文件之前检测输出内容能否由原编码表示。
        output.encode(encoding)
        if options.create_backup:
            shutil.copy2(path, next_backup_path(path))
        atomic_write_text(path, output, encoding)
        return FileResult(path=path, replacements=count, changed=True)
    except Exception as exc:
        return FileResult(path=path, error=f"{path}: {exc}")


def process_file(path: Path, options: ReplaceOptions) -> FileResult:
    prepared = prepare_rules(options)
    return _process_file(path, options, prepared)


def _aggregate(results: Iterable[FileResult]) -> BatchResult:
    batch = BatchResult()
    for item in results:
        batch.scanned_files += 1
        if item.error:
            batch.errors.append(item.error)
        elif item.changed:
            batch.changed_files += 1
            batch.total_replacements += item.replacements
            batch.changed_paths.append(item.path)
        else:
            batch.skipped_files += 1
    return batch


def process_single_file(path: Path, options: ReplaceOptions) -> BatchResult:
    prepared = prepare_rules(options)
    return _aggregate([_process_file(path, options, prepared)])


def process_folder(folder: Path, options: ReplaceOptions) -> BatchResult:
    # 先验证所有规则，防止第一个文件修改后才发现后续规则错误。
    prepared = prepare_rules(options)
    folder = folder.expanduser().resolve()
    if not folder.is_dir():
        if not folder.exists():
            raise FileNotFoundError(f"文件夹不存在：{folder}")
        raise ValueError(f"目标不是文件夹：{folder}")
    paths = sorted(
        (p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS),
        key=lambda p: p.name.casefold(),
    )
    return _aggregate(_process_file(p, options, prepared) for p in paths)
