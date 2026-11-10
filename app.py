"""PySide6 GUI：多规则普通/正则替换，保持单文件及批处理能力。"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from config_manager import AppConfig, ConfigManager
from replacer import ReplaceOptions, ReplaceRule, prepare_rules, process_folder, process_single_file

APP_TITLE = "Markdown / TXT 批量文本替换工具 v2.0"


@dataclass
class RuleRow:
    widget: QWidget
    number_label: QLabel
    source_edit: QLineEdit
    replacement_edit: QLineEdit
    regex_checkbox: QCheckBox
    remove_button: QPushButton


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.resize(920, 670)
        self.setMinimumSize(760, 560)
        self.config_manager = ConfigManager()
        self.config = self.config_manager.load()
        self.rule_rows: list[RuleRow] = []
        self._build_ui()
        self._load_config()
        self._update_mode_ui()

    def _build_ui(self) -> None:
        root = QWidget(self)
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setSpacing(10)

        mode_box = QGroupBox("1. 输入模式")
        mode_layout = QVBoxLayout(mode_box)
        mode_row = QHBoxLayout()
        self.file_radio = QRadioButton("单文件")
        self.folder_radio = QRadioButton("文件夹批处理（不递归）")
        self.mode_group = QButtonGroup(self)
        self.mode_group.addButton(self.file_radio)
        self.mode_group.addButton(self.folder_radio)
        mode_row.addWidget(self.file_radio)
        mode_row.addWidget(self.folder_radio)
        mode_row.addStretch(1)
        mode_layout.addLayout(mode_row)
        path_row = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.browse_button = QPushButton("选择…")
        path_row.addWidget(self.path_edit, 1)
        path_row.addWidget(self.browse_button)
        mode_layout.addLayout(path_row)
        layout.addWidget(mode_box)

        rule_box = QGroupBox("2. 替换规则（从上至下依次执行）")
        rule_box_layout = QVBoxLayout(rule_box)
        description = QLabel(
            "默认示例：将 \\( 和 \\) 分别替换为 $。不勾选时按原文本精确替换；勾选“正则”后支持 Python re 语法和捕获组。"
        )
        description.setWordWrap(True)
        rule_box_layout.addWidget(description)

        self.rule_scroll = QScrollArea()
        self.rule_scroll.setWidgetResizable(True)
        self.rule_scroll.setMinimumHeight(145)
        self.rule_scroll.setMaximumHeight(260)
        self.rule_container = QWidget()
        self.rule_layout = QVBoxLayout(self.rule_container)
        self.rule_layout.setContentsMargins(4, 4, 4, 4)
        self.rule_layout.setSpacing(7)
        self.rule_layout.addStretch(1)
        self.rule_scroll.setWidget(self.rule_container)
        rule_box_layout.addWidget(self.rule_scroll)

        rule_actions = QHBoxLayout()
        self.add_rule_button = QPushButton("＋ 添加一条替换规则")
        self.add_rule_button.clicked.connect(lambda: self._add_rule())
        rule_actions.addWidget(self.add_rule_button)
        rule_actions.addStretch(1)
        rule_box_layout.addLayout(rule_actions)
        layout.addWidget(rule_box)

        safe_box = QGroupBox("3. 文件处理")
        safe_layout = QFormLayout(safe_box)
        self.backup_checkbox = QCheckBox("修改前创建备份文件（推荐）")
        self.open_after_process_checkbox = QCheckBox("单文件处理完成后，用系统默认程序打开该文件")
        self.open_after_process_checkbox.setToolTip("仅单文件模式生效；即使没有匹配内容也可打开；文件夹处理不会自动打开。")
        safe_layout.addRow("", self.backup_checkbox)
        safe_layout.addRow("", self.open_after_process_checkbox)
        layout.addWidget(safe_box)

        button_row = QHBoxLayout()
        self.run_button = QPushButton("开始处理")
        self.run_button.setMinimumHeight(36)
        self.save_button = QPushButton("保存当前配置")
        button_row.addWidget(self.run_button)
        button_row.addWidget(self.save_button)
        button_row.addStretch(1)
        layout.addLayout(button_row)

        layout.addWidget(QLabel("4. 处理结果"))
        self.log_edit = QPlainTextEdit()
        self.log_edit.setReadOnly(True)
        layout.addWidget(self.log_edit, stretch=1)

        self.file_radio.toggled.connect(self._update_mode_ui)
        self.folder_radio.toggled.connect(self._update_mode_ui)
        self.browse_button.clicked.connect(self._browse)
        self.run_button.clicked.connect(self._run)
        self.save_button.clicked.connect(self._save_config_clicked)

    def _add_rule(self, rule: ReplaceRule | None = None) -> None:
        if rule is None:
            rule = ReplaceRule("", "", False)

        widget = QWidget(self.rule_container)
        row_layout = QHBoxLayout(widget)
        row_layout.setContentsMargins(0, 0, 2, 0)
        row_layout.setSpacing(7)

        number_label = QLabel()
        number_label.setFixedWidth(22)
        source_label = QLabel("原文本：")
        source_edit = QLineEdit()
        source_edit.setPlaceholderText(r"例如：\(")
        source_edit.setText(rule.source)
        source_edit.setMinimumWidth(110)
        target_label = QLabel("替换为：")
        target_edit = QLineEdit()
        target_edit.setPlaceholderText("可留空表示删除")
        target_edit.setText(rule.replacement)
        target_edit.setMinimumWidth(110)
        regex_checkbox = QCheckBox("正则")
        regex_checkbox.setToolTip("勾选后原文本采用 Python re 正则；替换为支持 \\1 / \\g<name> 捕获组引用。")
        regex_checkbox.setChecked(rule.regex)
        remove_button = QPushButton("删除")
        remove_button.setFixedWidth(56)
        for control in (number_label, source_label, source_edit, target_label, target_edit, regex_checkbox, remove_button):
            if control in (source_edit, target_edit):
                row_layout.addWidget(control, 1)
            else:
                row_layout.addWidget(control)

        row = RuleRow(widget, number_label, source_edit, target_edit, regex_checkbox, remove_button)
        remove_button.clicked.connect(lambda checked=False, record=row: self._remove_rule(record))
        self.rule_rows.append(row)
        self.rule_layout.insertWidget(self.rule_layout.count() - 1, widget)
        self._refresh_rule_numbers()

    def _remove_rule(self, row: RuleRow) -> None:
        if row not in self.rule_rows:
            return
        self.rule_rows.remove(row)
        self.rule_layout.removeWidget(row.widget)
        row.widget.hide()
        row.widget.deleteLater()
        self._refresh_rule_numbers()

    def _refresh_rule_numbers(self) -> None:
        for i, row in enumerate(self.rule_rows, start=1):
            row.number_label.setText(f"{i}.")
            row.remove_button.setEnabled(len(self.rule_rows) > 1)

    def _load_config(self) -> None:
        cfg = self.config
        (self.folder_radio if cfg.mode == "folder" else self.file_radio).setChecked(True)
        self.path_edit.setText(cfg.last_path)
        self.backup_checkbox.setChecked(cfg.create_backup)
        self.open_after_process_checkbox.setChecked(cfg.open_after_process)
        for rule in cfg.rules:
            self._add_rule(rule)

    def _collect_config(self) -> AppConfig:
        return AppConfig(
            mode="folder" if self.folder_radio.isChecked() else "file",
            last_path=self.path_edit.text().strip(),
            rules=[ReplaceRule(
                source=row.source_edit.text(),
                replacement=row.replacement_edit.text(),
                regex=row.regex_checkbox.isChecked(),
            ) for row in self.rule_rows],
            create_backup=self.backup_checkbox.isChecked(),
            open_after_process=self.open_after_process_checkbox.isChecked(),
        )

    def _options(self, cfg: AppConfig) -> ReplaceOptions:
        opts = ReplaceOptions(rules=tuple(cfg.rules), create_backup=cfg.create_backup)
        prepare_rules(opts)
        return opts

    def _update_mode_ui(self) -> None:
        is_folder = self.folder_radio.isChecked()
        self.path_edit.setPlaceholderText(
            "选择文件夹，仅处理当前层级的 .md / .markdown / .txt"
            if is_folder else "选择 .md / .markdown / .txt 文件"
        )
        self.open_after_process_checkbox.setEnabled(not is_folder)

    def _browse(self) -> None:
        path_text = self.path_edit.text().strip()
        p = Path(path_text).expanduser() if path_text else None
        if self.folder_radio.isChecked():
            start = str(p if p.is_dir() else p.parent) if p else ""
            selected = QFileDialog.getExistingDirectory(self, "选择文件夹", start)
        else:
            start = str(p.parent) if p else ""
            selected, _ = QFileDialog.getOpenFileName(
                self, "选择 Markdown / TXT 文件", start,
                "文本文件 (*.md *.markdown *.txt);;所有文件 (*.*)",
            )
        if selected:
            self.path_edit.setText(selected)

    def _open_with_system_default(self, path: Path) -> None:
        try:
            target = path.expanduser().resolve()
            if not target.is_file():
                self.log_edit.appendPlainText(f"[警告] 文件不存在，无法打开：{target}")
                return
            success = QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))
            if not success:
                self.log_edit.appendPlainText(f"[警告] 未能通过系统默认程序打开文件：{target}")
        except Exception as exc:
            self.log_edit.appendPlainText(f"[警告] 系统默认程序打开失败：{exc}")

    def _run(self) -> None:
        self.log_edit.clear()
        try:
            cfg = self._collect_config()
            if not cfg.last_path:
                raise ValueError("请先选择文件或文件夹。")
            options = self._options(cfg)
            self.config_manager.save(cfg)

            self.run_button.setEnabled(False)
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            try:
                path = Path(cfg.last_path)
                result = (
                    process_folder(path, options) if cfg.mode == "folder"
                    else process_single_file(path, options)
                )
            finally:
                QApplication.restoreOverrideCursor()
                self.run_button.setEnabled(True)

            self.log_edit.appendPlainText(f"扫描文件：{result.scanned_files}")
            self.log_edit.appendPlainText(f"修改文件：{result.changed_files}")
            self.log_edit.appendPlainText(f"替换次数：{result.total_replacements}")
            self.log_edit.appendPlainText(f"跳过文件：{result.skipped_files}")
            self.log_edit.appendPlainText(f"失败文件：{len(result.errors)}")
            if result.changed_paths:
                self.log_edit.appendPlainText("\n已修改文件：")
                for item in result.changed_paths:
                    self.log_edit.appendPlainText(f"  - {item}")
            if result.errors:
                self.log_edit.appendPlainText("\n错误详情：")
                for error in result.errors:
                    self.log_edit.appendPlainText(f"  - {error}")

            if result.errors:
                QMessageBox.warning(self, "处理完成（存在错误）", f"已替换 {result.total_replacements} 处；失败文件 {len(result.errors)} 个。")
            elif result.total_replacements == 0:
                QMessageBox.information(self, "处理完成", "未发现需要修改的内容，原文件保持不变。")
            else:
                QMessageBox.information(self, "处理完成", f"替换 {result.total_replacements} 处；修改 {result.changed_files} 个文件。")

            if cfg.mode == "file" and cfg.open_after_process and not result.errors:
                self._open_with_system_default(Path(cfg.last_path))
        except Exception as exc:
            self.run_button.setEnabled(True)
            self.log_edit.appendPlainText(f"[失败] {exc}")
            QMessageBox.critical(self, "处理失败", str(exc))

    def _save_config_clicked(self) -> None:
        try:
            cfg = self._collect_config()
            self._options(cfg)
            path = self.config_manager.save(cfg)
            QMessageBox.information(self, "配置已保存", f"配置文件：\n{path}")
        except Exception as exc:
            QMessageBox.critical(self, "保存失败", str(exc))

    def closeEvent(self, event) -> None:
        try:
            cfg = self._collect_config()
            self._options(cfg)
            self.config_manager.save(cfg)
        except Exception:
            pass
        super().closeEvent(event)


def main() -> int:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
