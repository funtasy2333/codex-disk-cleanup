# Codex Disk Cleanup

[![CI](https://github.com/funtasy2333/codex-disk-cleanup/actions/workflows/ci.yml/badge.svg)](https://github.com/funtasy2333/codex-disk-cleanup/actions/workflows/ci.yml)

为本地 Codex 构建的临时文件生命周期插件。Python 3.10+，运行时只用标准库。

发布版本为 **0.1.6**，支持自动发现新系统临时目录，以及审核、保留、确认隔离和恢复流程，scratch 为可选位置。默认只预览；显式启用隔离模式后，文件移入可恢复的隔离区。永久删除是独立操作。

230 项本地隔离测试通过；发布前核对跨平台 CI，升级后的原生 Hooks 验收另行记录。GitHub 公开发布不等于已上架 OpenAI 公共插件目录。

[English](docs/README.en.md) · [安全边界](SECURITY.md) · [设计](docs/design.md) · [验收记录](docs/validation.md)

## 功能与范围

| 功能 | 行为 |
| --- | --- |
| 新建文件追踪 | 匹配 Pre/Post 观察新建文件；范围为本会话 scratch、明确登记的项目临时目录，以及自动发现的新系统临时目录 |
| 自动整理 | SessionStart 提供受管位置说明并检查过期会话；Stop 整理当前回合；SessionEnd 整理结束会话 |
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
codex plugin marketplace add funtasy2333/codex-disk-cleanup --ref v0.1.6
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

从 0.1.3 起，手动预览会显示仍有 pending 工具的会话候选，保留完整路径、字节数和 `plan_id`；`blocked` 列出当前阻止隔离的路径和原因。`bytes` 包含这些被阻止的候选，并不表示现在能够释放的空间。文件已修改、未到保留期限或不属于所选会话时，仍按原规则过滤。`status` 新增 `pending_sessions`，显示有效租期内每个会话的工具数和最早开始时间；`pending` 仍统计全部记录，包括等待正常 Hook 过期整理的记录。

预览可见不等于允许移动。真正执行隔离时仍拒绝有有效 pending 工具的会话，包括原生执行命令自身的工具租期。遇到此提示，应等工具结束后，通过已授权的生命周期流程或独立终端执行；不能删除 pending 记录来绕过保护。预览模式下的生命周期计划同样显示被阻止的候选，自动隔离模式则跳过并记录原因。

Windows 将上面的 `python3` 换为 `py -3`，并使用 PowerShell 对应的路径变量语法。


## 0.1.6：审核候选的处理流程

0.1.6 新增以下人工审核流程。安装后需重启再验证原生会话；发布和安装本身不处理实际审核候选。

1. **展示文件及用途**：`review-list --session SESSION_ID` 只读展示文件路径、大小、观察来源、状态和人工说明的用途。尚未说明的用途显示为空，不能把观察来源当作已证实用途。列表包含当前身份和 `snapshot`；文件变化后必须重新展示、审核。
2. **标记保留或隔离**：`review-mark` 指定会话、候选 ID、当前 snapshot、`keep` 或 `quarantine` 及非空用途说明。此步仅记决策，不移动文件。保留标记同时阻止该路径的自动隔离。
3. **确认清单**：`review-plan --session SESSION_ID` 列出该会话标记为隔离的文件、用途、数量、总大小、阻止原因、计划 ID 和摘要。重复 `--candidate ID` 可明确选择子集。计划十五分钟内有效、只能使用一次；确认范围必须是展示出的确切文件。
4. **核验并隔离**：`review-apply PLAN_ID --digest DIGEST --yes` 重新核对决策、观察记录、父目录身份、文件内容指纹、保留标记及 pending 访问，变化或失效的文件跳过并说明原因。普通 `quick --apply` 无法绕过审核摘要确认。
5. **恢复**：`restore QUARANTINE_ID` 恢复到原路径，拒绝覆盖。恢复后自动标记保留；候选列表被更新或移除也不丢失已隔离文件的恢复依据。`purge ID --yes` 仍是另行授权的永久删除。

```sh
python3 "$PLUGIN_DIR/scripts/cleanup.py" --data "$DATA_DIR" review-list --session SESSION_ID
python3 "$PLUGIN_DIR/scripts/cleanup.py" --data "$DATA_DIR" review-mark --session SESSION_ID --candidate CANDIDATE_ID --snapshot SNAPSHOT --decision keep --purpose "需要保留的源材料"
python3 "$PLUGIN_DIR/scripts/cleanup.py" --data "$DATA_DIR" review-mark --session SESSION_ID --candidate CANDIDATE_ID --snapshot SNAPSHOT --decision quarantine --purpose "已完成任务的一次性渲染检查"
python3 "$PLUGIN_DIR/scripts/cleanup.py" --data "$DATA_DIR" review-plan --session SESSION_ID --candidate CANDIDATE_ID
python3 "$PLUGIN_DIR/scripts/cleanup.py" --data "$DATA_DIR" review-apply PLAN_ID --digest DIGEST --yes
python3 "$PLUGIN_DIR/scripts/cleanup.py" --data "$DATA_DIR" restore QUARANTINE_ID
```

明确确认的人工清单允许立即隔离这些文件，不改变自动发现目录的七天保留期限、隔离策略或登记项目目录。混合目录中只处理点名文件，邻近成果保留。隔离区位于所选文件的直接父目录 `.codex-disk-cleanup-quarantine/`，空间需永久删除后才释放。

审核计划展示被 pending 阻止的项；执行仍检查同一会话、其他会话对父目录的明确访问，以及旧版或缺少工作目录时的未知访问。旧记录的未知访问在正常工具结束或租期到期前阻止人工隔离，不得删租约来绕过。原生执行命令可能因自身租约被阻止，应待工具结束后在已授权范围内通过独立终端执行。没有从候选名单自动判断一次性用途或批量批准的行为。

## 0.1.5：直接观察临时文件位置

0.1.5 新增以下行为，安装后需重启再验证原生会话。会话无需改用 scratch：插件从工具输入的字面路径自动发现本次会话新出现的专用系统临时目录，后续匹配工具调用继续观察该目录的新文件。scratch 保留为可选受管位置。

- 只检查工具明确引用的路径；允许 stdlib 系统临时位置和 POSIX `/tmp` 的系统别名，不扫描整个临时区。相对路径结合绝对 cwd 解释；不执行任意代码，不从工具输出推定创建权。随机生成且未在输入中出现的目录无法自动归属。
- Pre 记录此前不存在的目录候选与现存父目录/base 身份，Post 校验实际目录、会话、工具调用、回合和设备号/inode。已存在或共享目录不会自动收编；链接、Git、敏感路径、Codex 数据和重叠受管目录继续保护。
- 首次发现目录时已有的文件只记录为 `review_candidates`，不会进入自动清理计划。后续有完整前后快照的新文件才可进入 tracking。初次命令即使部分失败，也只绑定观察到的目录和审核候选，不能取得初始文件的清理权；失败的后续调用不收编文件。
- 自动发现目录绑定一个会话，固定保留 **7 天**，覆盖 `test_*` 零天规则；隔离继续受 pending、身份和指纹检查约束。另一会话明确访问同一临时目录时，也阻止隔离；重叠访问令新增归属证据失效，即使另一工具先结束也不借用它的文件。
- 每阶段共用 2000 个目录项预算；每会话最多 16 个发现目录，全局最多 2000 个目录记录，审核候选最多 2000 条。超限、访问失败或身份变化暂停新增收编并报告原因，不扩大扫描。工具参数超限时保留访问范围未知的 pending 记录，工具结束前阻止所有隔离；并发调用的创建证据同时失效。

`status` 增加 `discover_temp`、`discovered_temp`、`discovered_temp_errors` 和 `review_candidates`。审核候选只有元数据，没有内容读取/SHA，也不构成清理授权；普通项目中明确路径的文件可进入该清单，任意代码生成的项目文件不作完整覆盖承诺。生成图源缓存仍使用独立的 `generated-preview` 核对。

```sh
# 独立控制临时目录发现；保留现有 auto 模式与清理策略
python3 "$PLUGIN_DIR/scripts/cleanup.py" --data "$DATA_DIR" init --discover-temp off
python3 "$PLUGIN_DIR/scripts/cleanup.py" --data "$DATA_DIR" init --discover-temp on
# 撤销一个目录的观察授权；不移动文件，也不删除历史追踪记录
python3 "$PLUGIN_DIR/scripts/cleanup.py" --data "$DATA_DIR" forget-temp --root /absolute/temp/task --yes
```

发现功能默认开启，但不改变 `auto`。关闭功能使已有发现目录的移动计划失效，仍可恢复隔离文件。存在未恢复/未处理的隔离记录时，`forget-temp` 拒绝撤销，需先恢复、明确 purge 或完成恢复核对。SQLite schema 1 保持兼容，新增独立状态表，旧数据的只读 status 不创建表。

现有 `/private/tmp/pfas-formal-review` 等历史目录不会回补创建记录或自动清理。修改仅影响升级后的未来调用，不能把目录里现存文件等同于本会话所有的临时文件。

## 0.1.4：项目临时目录与动态路径

0.1.4 增加项目临时目录与动态路径覆盖。完整新版原生 Hooks 生命周期验收仍待升级、重启后进行。

创建文件前先按用途确定位置：临时脚本、局部裁剪、渲染核对图、参考拼版、暂存副本写入 scratch；正式文件、可复用编辑素材、源提示词与审查证据保留在项目。被替代的尝试若已明确作为审查证据保留，不能仅因文件名是“初稿”就视作一次性文件。

0.1.4 的匹配 PreToolUse/PostToolUse 除字面路径外，还对授权目录作有限的存在性快照，因此 Python 循环、变量拼接路径也可被追踪。不执行或解析任意代码，不从工具输出推定删除权。每个阶段在所有根目录间共用 2000 个目录项预算；超限、访问失败、不同回合重叠或旧格式 pending 存在时，新增追踪暂停（包括字面路径），并记录 `coverage-skipped`。

也可明确登记某一会话的专用项目临时子目录。目录必须事先存在，不能是整个项目或混有成品/审查材料的制作目录。示例中的目录与会话 ID 都应替换为实际值：

```sh
python3 "$PLUGIN_DIR/scripts/cleanup.py" --data "$DATA_DIR" enroll \
  --project /absolute/project --root /absolute/project/.tmp/session-id \
  --session ACTUAL_SESSION_ID --days 7 --yes
python3 "$PLUGIN_DIR/scripts/cleanup.py" --data "$DATA_DIR" unenroll \
  --root /absolute/project/.tmp/session-id --yes
```

登记绑定目录设备号/inode及会话，最多 16 个根目录，不允许重叠；不会自动收编已有文件，也不改变 auto 模式。项目临时目录按明确的 `--days` 保留期限处理，覆盖 `test_*` 文件名的零天规则；默认 7 天，明确设置 `--days 0` 才立即满足保留期限。取消登记不移动文件，并使旧计划失去授权。不存在或身份已变化的根目录会在 `status.project_scratch_errors` 中报告，仍可通过 unenroll 取消。

原有 Git 树、数据库、配置、链接/硬链接及成品路径保护继续生效。Git 项目使用插件提供的外部 scratch，不把 Git 树加入清理。隔离、恢复、永久删除的确认与身份检查继续适用；默认仍只预览。宿主生成图片的源缓存不自动登记或清理；使用下述独立只读命令核对。历史项目文件只可先制作审查候选清单，不能补造创建记录。

### 宿主生成图副本核对

图片工具会将原始输出保存在 `CODEX_HOME/generated_images/会话ID/`。项目中另存素材后，这里仍可能保留完全一致的副本。0.1.4 提供独立的只读核对命令：

```sh
python3 "$PLUGIN_DIR/scripts/cleanup.py" generated-preview \
  --session ACTUAL_SESSION_ID --copy-root /absolute/project/saved-images
```

`--copy-root` 可重复指定实际归档目录；不提供时只列出该会话源图，不推断已有备份。自定义源位置可指定 `--codex-home ABS_CODEX_HOME`。源范围固定为该 home 的 `generated_images/实际UUID/`，不扫描其他会话或整个 Codex 数据。副本目录必须明确给出，且位于 Codex home 外，也不能包含该 home。

输出每张源图的路径、字节数、指纹和 SHA-256 完全一致的副本路径。相同内容标为 `verified-duplicate-review-required`，没有匹配副本标为 `no-copy-verified`。匹配副本只说明内容已经另存，不说明原路径不再用于会话展示或编辑。

这个命令不创建插件状态或追踪记录、不生成可执行的 `plan_id`、不接受 apply/purge，也不移动或删除文件。它补齐宿主生成图的候选检查通道，保留人工审核；不能把同名文件或一次文件列表当作删除授权。

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
