# Markdown Delimiter Replacer

一款免费、开源的 **Markdown / TXT 多规则批量文本替换工具**，使用 Python + PySide6 编写。
支持普通文本替换与逐条独立配置的正则表达式替换；面向论文公式分隔符调整、Markdown 清理以及一般文本批处理。

**当前版本：** v2.0.0 · **许可证：** [MIT](LICENSE) · **语言：** 中文 GUI

## 功能

- **多条规则**：每条独立填写“原文本 → 替换为”，可以添加或删除，按界面从上往下执行。
- **普通 / 正则模式**：每行有独立的“正则”复选框；默认普通模式，不会将 `\`、括号、点号等当作正则语法。
- **单文件 / 文件夹**：支持 `.md`、`.markdown`、`.txt`；文件夹模式不递归子文件夹。
- **安全写入**：修改前可自动备份（默认开启）；原子写入，不覆盖历史 `.bak` 备份；无变化时不写入。
- **单文件自动打开**：处理完成后可使用系统默认程序打开（默认开启）；文件夹模式不会自动打开。
- **配置持久化**：启动后在程序所在目录生成或读取本地 `config.json`，保留规则和界面选项；支持 v1.x 配置迁移。
- **编码**：支持 UTF-8、UTF-8 BOM 和 GB18030；保留原有换行字符（LF / CRLF）。

## 默认规则

| 原文本 | 替换为 | 正则 |
|---|---|---|
| `\(` | `$` | 否 |
| `\)` | `$` | 否 |

例如输入 `\(x + 1\)`，输出 `$x + 1$`。

**规则顺序很重要。** 后面的规则处理的是前面规则修改过的内容。
勾选“正则”后，原文本使用 Python `re` 语法，替换文本支持 `\1`、`\g<name>` 等组引用；普通模式则使用精确文本替换。

## 快速开始

建议使用 Python 3.11 或 3.12。在 Windows PowerShell 中：

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

也可以在 VS Code / PyCharm 中选择虚拟环境里的 `python.exe` 后直接运行 `app.py`。

> 程序首次运行**不需要** `config.json`：若文件不存在将使用内置默认规则；保存设置或关闭窗口后才写入。仓库只提供无用户路径的 [`config.example.json`](config.example.json)。
>
> `config.json` 中的 `last_path` 可能包含本机用户名和文件路径，已被 `.gitignore` 排除。**不要把它手工提交到公开仓库。**

## 使用说明

1. 选择“单文件”或“文件夹批处理”，选择目标路径。
2. 根据需要增删替换规则；只有勾选某行“正则”时该行才使用正则表达式。
3. 根据需要勾选“修改前创建备份文件”和“单文件完成后打开”。
4. 点击“开始处理”，在下方日志区检查扫描、修改、替换次数与错误。

注意：默认规则只替换字面上的 `\(` 和 `\)`，并非针对所有 LaTeX 文本进行语法转换。处理重要文件前建议先备份并通过少量样本验证。正则表达式编写不当可能造成运行缓慢或意外匹配。

## Windows EXE 打包

在 **Windows** 环境下安装项目依赖后，在仓库根目录执行：

```powershell
python -m PyInstaller --noconfirm --clean MarkdownDelimiterReplacer.spec
```

或者双击 `scripts/build_onefile.bat`。生成的单文件 GUI 程序为：

```text
dist/MarkdownDelimiterReplacer.exe
```

该构建采用 `console=False`，正常启动时不会附带控制台窗口。最终用户运行 EXE 无须预装 Python；但配置文件默认保存在 EXE 同目录，建议将 EXE 放在可写目录。PyInstaller 不支持跨操作系统直接构建 Windows EXE。

## 测试

```powershell
python -m unittest discover -s tests -v
```

测试包括：多条普通/正则替换、规则顺序、非法正则、防止备份覆盖、编码/换行保留、文件夹非递归处理、配置迁移及 Qt GUI 控件交互等。安装 PySide6 后，Qt 测试会使用 `QT_QPA_PLATFORM=offscreen` 无界面运行。

> 维护说明：自动测试能够覆盖核心规则与文件操作；实际发布 EXE 前，仍应在目标 Windows 版本上人工检查 GUI、系统默认程序打开、文件权限及 Windows Defender 提示。

## 项目结构

```text
.
├── app.py                         # PySide6 图形界面
├── replacer.py                    # 替换规则与文件处理核心
├── config_manager.py              # 配置持久化与旧版兼容
├── config.example.json            # 不包含个人路径的配置示例
├── requirements.txt               # 运行 / 打包依赖
├── MarkdownDelimiterReplacer.spec  # 单文件 GUI 打包配置
├── scripts/build_onefile.bat      # Windows 打包脚本
├── tests/                          # 自动化测试
├── .github/workflows/ci.yml       # 持续集成
├── .gitignore
└── LICENSE
```

## 开源与贡献

采用 [MIT License](LICENSE)，允许在保留原版权声明和许可证的条件下使用、修改及再分发。欢迎通过 Issue 反馈问题，或通过 Pull Request 提交经过测试的改进。

本项目不需要网络服务，也不主动上传用户文件；替换操作在本地完成。使用前请确认待处理文件的来源及操作权限。
