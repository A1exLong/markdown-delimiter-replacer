"""配置持久化与 v1.x 配置兼容迁移。"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

from replacer import DEFAULT_RULES, ReplaceRule, prepare_rules, ReplaceOptions


@dataclass
class AppConfig:
    mode: str = "file"
    last_path: str = ""
    rules: list[ReplaceRule] = field(default_factory=lambda: list(DEFAULT_RULES))
    create_backup: bool = True
    open_after_process: bool = True


def application_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _migrate_legacy_rules(data: dict) -> list[ReplaceRule]:
    """将旧版“头+内容+尾”规则迁移为等价的单条正则替换。"""
    head = data.get("input_head", "[")
    tail = data.get("input_tail", "]")
    if not isinstance(head, str) or not head or not isinstance(tail, str) or not tail:
        return list(DEFAULT_RULES)

    nl = r"(?:\r\n|\n|\r)"
    start = nl if data.get("require_newline_after_head", True) else ""
    end = nl if data.get("require_newline_before_tail", True) else ""
    pattern = re.escape(head) + start + r"(.*?)" + end + re.escape(tail)
    flags = "si" if data.get("ignore_case", False) else "s"
    pattern = f"(?{flags}:{pattern})"

    out_head = data.get("output_head", "$$")
    out_tail = data.get("output_tail", "$$")
    if not isinstance(out_head, str) or not isinstance(out_tail, str):
        return list(DEFAULT_RULES)

    # 避免旧版替换文本中的反斜杠被新正则当作非法转义。
    replacement = out_head.replace("\\", "\\\\") + r"\g<1>" + out_tail.replace("\\", "\\\\")
    return [ReplaceRule(source=pattern, replacement=replacement, regex=True)]


class ConfigManager:
    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path is not None else application_dir() / "config.json"

    def load(self) -> AppConfig:
        if not self.path.is_file():
            return AppConfig()
        try:
            obj = json.loads(self.path.read_text(encoding="utf-8-sig"))
            if not isinstance(obj, dict):
                return AppConfig()

            if isinstance(obj.get("rules"), list):
                rules = []
                for item in obj["rules"]:
                    if not isinstance(item, dict):
                        raise ValueError("规则结构无效")
                    source = item.get("source")
                    replacement = item.get("replacement")
                    regex = item.get("regex", False)
                    if not isinstance(source, str) or not isinstance(replacement, str) or type(regex) is not bool:
                        raise ValueError("规则内容类型无效")
                    rules.append(ReplaceRule(source, replacement, regex))
            elif "input_head" in obj:
                rules = _migrate_legacy_rules(obj)
            else:
                rules = list(DEFAULT_RULES)

            # 配置格式错误时以安全默认值恢复；而不是吞掉错误留在处理阶段。
            prepare_rules(ReplaceOptions(rules=tuple(rules)))

            mode = obj.get("mode", "file")
            if mode not in ("file", "folder"):
                mode = "file"
            last_path = obj.get("last_path", "")
            return AppConfig(
                mode=mode,
                last_path=last_path if isinstance(last_path, str) else "",
                rules=rules,
                create_backup=obj.get("create_backup", True) is not False,
                open_after_process=obj.get("open_after_process", True) is not False,
            )
        except (OSError, UnicodeError, ValueError, TypeError, json.JSONDecodeError, re.error, IndexError):
            return AppConfig()

    def save(self, config: AppConfig) -> Path:
        prepare_rules(ReplaceOptions(rules=tuple(config.rules)))
        content = json.dumps(asdict(config), ensure_ascii=False, indent=2) + "\n"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=".config.", suffix=".tmp", dir=str(self.path.parent))
        tmp = Path(temp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as file:
                file.write(content)
                file.flush()
                os.fsync(file.fileno())
            os.replace(tmp, self.path)
        except Exception:
            tmp.unlink(missing_ok=True)
            raise
        return self.path
