# Codex Disk Cleanup

[![CI](https://github.com/funtasy2333/codex-disk-cleanup/actions/workflows/ci.yml/badge.svg)](https://github.com/funtasy2333/codex-disk-cleanup/actions/workflows/ci.yml)

为本地 Codex 构建的临时文件生命周期插件。Python 3.10+，运行时只用标准库。

**0.1.2 修复了 Hooks 注册及 SessionEnd 超时配置的兼容性问题，尚未经过长期使用验证。** 默认只预览；自动清理需显式启用，清理先移入隔离区，可恢复。永久删除是独立操作。源码、测试、CI 和安装包都在本仓库，GitHub 公开发布不等于已上架 OpenAI 公共插件目录。

[English](docs/README.en.md) · [安全边界](SECURITY.md) · [设计](docs/design.md) · [验收记录](docs/validation.md)

## 功能与范围

| 功能 | 行为 |
| --- | --- |
| 新建文件追踪 | PreToolUse 记录路径不存在，匹配的 PostToolUse 验证实际创建；只追踪本会话专用 scratch 目录 |
| 自动整理 | SessionStart 提供临时目录并检查过期会话；Stop 整理当前回合；SessionEnd 整理结束会话 |
| 默认预览 | 不移动文件；显式配置 `auto: quarantine` 后才自动隔离 |
| 手动维护 | `deep` 检查明确登记的 `CODEX_HOME/cache`、`CODEX_HOME/logs` 子树，保留期限默认 30 天 |
| 可恢复清理 | 隔离区位于源文件所属根目录，避免跨磁盘搬移；`restore` 不覆盖已有文件 |
| 永久删除 | 逐个隔离项执行 `purge ID --yes` 后才释放磁盘空间；没有自动永久删除 |
| 可靠状态 | SQLite WAL、事务、审计记录、过期预览失效、操作意图记录及崩溃恢复 |

不扫描整个磁盘，不清理任意项目，不处理 npm/pip/浏览器缓存，也不删除目录。
保护 Git 工作树（包括未跟踪文件）、交付目录、认证/配置、会话、记忆、技能、插件、数据库、密钥、符号链接、Windows reparse points 和硬链接。

## 安装

面向支持命令型 Hooks 的本地 Codex CLI / Desktop。需要 `python3`（macOS/Linux）或 `py -3`（Windows）。

在支持插件命令的 Codex CLI 中：

```sh
codex plugin marketplace add funtasy2333/codex-disk-cleanup --ref v0.1.2
codex plugin add codex-disk-cleanup@codex-disk-cleanup-marketplace
```

Desktop 可添加该 Git marketplace 后选择安装，或使用 Releases 中的插件 ZIP 按当前客户端支持的本地插件流程导入。
**安装并不代表 Hooks 已获得信任。** 按客户端显示的 Hook 审阅流程检查命令和脚本，再信任该定义；新版本变更后可能需要重新审阅。本项目不会修改你的全局配置或绕过信任检查。

**升级时先停止活跃聊天，完成版本更新后重启 Desktop。** 当前宿主更新缓存后，已有聊天可能仍引用旧版本脚本，造成工具和 Stop Hook 的缺失文件错误；重启后加载新版定义。不要直接编辑缓存或信任记录。

安装后在新聊天请求“查看 disk-cleanup 状态”。SessionStart 应提供该会话的专用临时目录。永久测试和最终交付仍放在项目中。
Hook 获得的 `PLUGIN_DATA` 是插件状态目录。普通工具不一定继承该变量；已安装脚本会核验原生缓存路径和清单，并解析该安装实例的数据目录。直接运行 `status` 可查看 `data`、`data_source`、`initialized` 和 `hooks_seen`；未初始化时不会创建数据目录，也不代表 Hooks 已运行。源码独立运行时用自选 `--data`，不能把独立状态误认成安装实例。

当前原生加载器跳过根目录 Agent Plugins `plugin.json` 的 Hooks，因此实际分发包仅使用 `.codex-plugin/plugin.json`。Portable 清单保留在 `docs/examples/` 作参考，不进入安装包。见[兼容性证据](docs/provenance.md)。设置 → 钩子中应出现 Codex Disk Cleanup 的五个 Hooks；缺失时刷新列表，并核对是否仍安装 v0.1.0。

当前官方说明：带 Hooks 的插件应手动分发，暂不能提交公共插件目录；云端编排的 Work 不支持本地命令型插件 Hooks，即使工具在本地执行。本地编排和执行的受支持环境可使用。
参见 [Hooks](https://learn.chatgpt.com/docs/hooks)、[插件包规范](https://developers.openai.com/plugins/build/plugins)、[分发限制](https://developers.openai.com/plugins/guides/submit-claude-plugin)。

## 命令

下面的 `PLUGIN_DIR` 指实际插件目录。先运行不带 `--data` 的 `status`，确认 `data_source` 为 `codex-installation` 或宿主环境来源，然后把返回的 `data` 作为 `DATA_DIR`。源码目录下可用自选专用数据目录运行独立实例。

```sh
python3 "$PLUGIN_DIR/scripts/cleanup.py" status
python3 "$PLUGIN_DIR/scripts/cleanup.py" --data "$DATA_DIR" dry-run --scope quick
python3 "$PLUGIN_DIR/scripts/cleanup.py" --data "$DATA_DIR" dry-run --scope deep
```

预览返回完整候选路径、字节数和 `plan_id`，有效期 15 分钟。查看候选后执行：

```sh
python3 "$PLUGIN_DIR/scripts/cleanup.py" --data "$DATA_DIR" quick --apply PLAN_ID --yes
python3 "$PLUGIN_DIR/scripts/cleanup.py" --data "$DATA_DIR" restore QUARANTINE_ID
python3 "$PLUGIN_DIR/scripts/cleanup.py" --data "$DATA_DIR" purge QUARANTINE_ID --yes
python3 "$PLUGIN_DIR/scripts/cleanup.py" --data "$DATA_DIR" recover
python3 "$PLUGIN_DIR/scripts/cleanup.py" --data "$DATA_DIR" audit
```

普通 `quick`、`deep` 也是预览。`--session SESSION_ID` 可明确选定当前会话；没有该参数的手动预览跳过仍活跃的会话。清理前会再次检查规则、文件身份、时间和 SHA-256；内容变化或新增 pending 工具时跳过。失效计划应重新预览。

Windows 将上面的 `python3` 换为 `py -3`，并使用 PowerShell 对应的路径变量语法。

## 启用自动隔离

默认配置由 `init` 创建；未创建配置时同样按预览模式运行。显式启用：

```sh
python3 "$PLUGIN_DIR/scripts/cleanup.py" --data "$DATA_DIR" init --auto quarantine
```

恢复预览模式：`init --auto preview`。`init` 保留已有维护目录设置。

| 专用 scratch 中的文件 | 保留规则 |
| --- | --- |
| `test_*`、`tmp_test_*` | 当前回合 Stop 或本会话 SessionEnd 时可隔离，前提是未发生修改且没有 pending 工具 |
| 其他已追踪文件 | 创建后保留 7 天 |
| `cron-output/` 下已追踪文件 | 创建后保留 14 天 |

会话在每次 Hook 更新活跃记录。SessionStart 只补扫已经结束或超过 24 小时无 Hook 的旧会话；不会清理别的活跃会话。未完成工具的记录保留 24 小时。这里的“活跃”是插件观测到的租期，不是操作系统进程探测；超长任务请保持预览模式。

文件必须在本会话 scratch 目录中，且由具有相同 `session_id`、`tool_use_id` 的前后 Hook 证明新建。文件名只决定保留类别，不能单独作为删除依据。复杂 shell/Python 动态生成路径可能无法追踪；不会解析工具输出、执行命令或补扫未知文件。

## 缓存和日志维护

在实际 `$DATA_DIR/config.json` 中明确登记，例如 macOS 默认 Codex home 下的日志目录（替换示例用户名）：

```json
{
  "schema": 1,
  "auto": "preview",
  "maintenance": [
    {"path": "/Users/yourname/.codex/logs", "kind": "logs", "days": 30},
    {"path": "/Users/yourname/.codex/cache", "kind": "cache", "days": 30}
  ]
}
```

仅添加实际存在的目录。支持自定义 `CODEX_HOME`，但配置、预览及执行应使用一致的环境。根目录必须处于该 home 的 `cache/` 或 `logs/` 内；宽泛 home、文档目录和项目目录会被拒绝。
日志只选择 `.log`、`.jsonl`、`.txt`；数据库和控制文件始终保护。按 mtime 与 ctime 中较新的时间计算期限，避免清理刚轮转/复制的日志。维护仅通过手动 `deep` 预览与执行，不由 Hooks 自动触发。
活动文件仍可能被不受本插件观测的进程打开，尤其在 POSIX 上。维护前关闭写入目标目录的应用；自动模式只管理 scratch。

## 开发与验证

```sh
python3 -m unittest discover -s tests -v
python3 tools/package.py --check
python3 tools/package.py
```

CI 在 macOS、Windows、Linux 以及 Python 3.10/3.13 上运行。插件 ZIP 只包含 `plugins/codex-disk-cleanup/`，不含本机状态、会话或项目文件。完整开发源码保留在仓库。详细验收边界见 [validation.md](docs/validation.md)。

设计参考 Hermes `disk-cleanup` 的创建证据、分类与保留策略，运行时为独立重写，不依赖 Hermes。参见 [来源与许可](docs/provenance.md)。MIT License。
