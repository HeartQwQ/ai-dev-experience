# graphify 与 codegraph：本地双图谱与 Hook 硬门禁

## 必须满足的条件

两个 CLI 均可运行，索引属于当前 Git monorepo 根，源文件/配置与索引记录一致，`graphify` 原生网状图已生成且渲染依赖本地化并通过完整性校验。查询代码时必须双图谱实际分析，随后阅读命中源码核实。文本检索用于精确文本补充，不能替代图谱门禁。

该要求是项目级硬规则。失败时先修复环境/索引，不以“工具不可用”为由改成纯搜索。本包同时提供 CLI 门禁（`scripts/graph_gate.py`）与宿主生命周期钩子门禁（`scripts/hook_gate.py` + `.agents/hooks.json`），在 `READY` 阶段自动拦截未完成双图谱查询前的业务源码搜索与读取。

## 安装与接入

graphify 的包名是 `graphifyy`，CLI 是 `graphify`；按官方稳定版本解析结果，用 `uv` 隔离工具环境安装，不误装同名近似包。codegraph 使用 `@colbymchenry/codegraph` 或官方对应平台发行物，按实际 engine 与 OS 核对；命令解析后复核 `--version`。

```text
uv tool install graphifyy
pnpm add --global @colbymchenry/codegraph@latest
graphify --version
codegraph --version
```

上面展示首次解析方式，实际落地应记录并固定解析版本；已有工具不未经检查反复全局升级。若 pnpm global 目录未配置，可按官方支持方式设置该安装环境，或使用受控用户级工具前缀，不改变无关项目的运行时。

本插件使用本地 CLI 完成门禁，因此不依赖 MCP 才能查询。需要集成助手 UI 时，graphify 的助手 Skill 安装、CLI、MCP 是不同步骤；选择项目级接入，不运行会改所有助手配置的全局自动探测：

```text
graphify install --project --platform codex
codegraph install --print-config codex
```

先查看输出与当前宿主支持位置，合并所需配置，保留已有设置。原生 MCP 接入按上游当前文档、实际绝对路径与项目根设置，并重启/重新加载后确认工具可调用。助手安装步骤不能代替逐项目索引，也不自动授权多 Agent。

## graphifyy 必须本地运行

每次图谱命令固定 `GRAPHIFY_BACKEND=none`、`GRAPHIFY_NO_AUTO_REFRESH=1`、`GRAPHIFY_QUERY_LOG_DISABLE=1`，抽取使用 `--code-only`。即使进程继承了某云服务 API key，也不能触发文档语义提取或自动选择远端后端。默认不启用 Cloud、云端 MCP、文档/媒体 LLM、远端数据库扫描和上传。

codegraph 使用本地索引，并以 `CODEGRAPH_TELEMETRY=0`、`DO_NOT_TRACK=1` 关闭本次进程统计。项目内的查询证据落到忽略的 `.dev-spec/local/`，不将其提交或外发。

“本地运行”覆盖解析、索引、查询和网状图查看。初次安装依赖及下载可视化静态库可能需要联网；不会把项目内容作为下载请求上传。离线已有缓存时复用，缺依赖时失败，不回退云服务。

## 构建、网状图与查询

```text
python tools/dev-spec/graph_gate.py build --root .
python tools/dev-spec/graph_gate.py check --root .
python tools/dev-spec/graph_gate.py query --root . --question "本次入口和调用关系"
```

在插件源码中直接运行时，将上面脚本路径替换为本 Skill 的 `scripts/graph_gate.py`。

`build` 执行 `graphify` 本地抽取和 `graphify export html`，同时初始化/同步 `codegraph`。产物包含 `graphify-out/graph.json`、`graphify` 原生 `graph.html`、`.codegraph/codegraph.db` 和 `.dev-spec/local/graph-state.json`；配置 `CODEGRAPH_DIR` 的环境使用其对应本地目录。

原生 HTML 依赖远程 CDN 的 `vis-network` 脚本。`graph_gate.py` 会自动匹配任意 CDN 域名的可视化脚本并下载到 `graphify-out/vendor/`，校验原生 HTML 的 SRI（存在时），保存来源/SHA256 元数据（`.source.json`）并改为本地相对引用。仍有远程资源、资源缺失、哈希不一致时门禁失败；禁止保留 CDN 当静默回退。

生成后通过本地 HTTP 查看器打开 `graphify-out/graph.html`，检查节点、连线、搜索、点击与导航；资源全在本地，查看不依赖 CDN。大图可能被上游聚合，需检查是否覆盖本次任务，不能将聚合图当作全部符号明细。HTML 生成成功与视觉交互验收分开报告。项目一键预览会启动本地图查看器并打开网状图与应用页面。

`query` 先校验本地状态，再调用 `graphify query` 与 `codegraph explore`，最后重新检查源指纹并保存结果至 `.dev-spec/local/last-query.json`。调用成功不代表所有相关代码都已覆盖：确认返回了实际路径、符号和有意义关系，再读真实源码；无关或空命中要细化问题、核对语言/忽略范围并修复。

## 系统级生命周期 Hook 门禁（`hook_gate.py`）

`init_monorepo.py` 自动在项目 `.agents/hooks.json` 配置 `PreToolUse` 与 `Stop` 钩子（本插件根目录同样提供 `hooks.json`）：

- **`PreToolUse` 拦截**：当项目处于 `READY` 阶段且 Agent 调用代码检索工具（如 `grep_search`、`find_by_name`）或直接读取 `apps/`、`packages/`、`crates/`、`src/`、`src-tauri/` 下的业务源码时，`hook_gate.py` 会实时校验 `.dev-spec/local/graph-state.json` 与 `last-query.json` 的有效性及指纹一致性。若未通过，直接返回 `decision: "deny"` 阻断调用。
- **`Stop` 拦截**：当对话回合正常结束（`NO_TOOL_CALL`）时，检查 `.dev-spec/local/dev-supervisor.pid` 是否残留未退出的预览守护进程，防止遗留后台孤儿服务。
- 自检命令：`python tools/dev-spec/hook_gate.py --self-test`。

## 新鲜度与失败处理

脚本根据 Git 可见的源文件/清单、忽略配置、工具版本、根路径和 graphify 产物生成指纹（包含文件数与字节数，安全解析仓库内符号链接并阻断越界软链或 >32 MiB 异常大文件）。源文件、版本、分支内容或配置变化后必须刷新；代码图谱的自动同步只是辅助，不替代此检查。构建期间源码改变也不放行。

索引排除依赖、制品、真实 env、运行数据和图谱自身，不能因过度排除失去真实应用。脚本的指纹不是语言覆盖证明；特殊扩展、生成源码、动态路由、宏和反射要核对工具实际支持。

发现工具缺失、索引损坏、锁冲突、解析失败或结果不完整时：保留诊断，确认写者与平台，修复/重建，再查询验证。不要默认删除锁、强制覆盖较小图、开启 LLM 或跳过另一工具。空项目只可先生成最小骨架，不能记录“零节点=分析通过”。

Windows/WSL 不共用活动 SQLite 索引；按上游支持分离 `.codegraph` 与 `.codegraph-wsl`，保持各自 PATH 和本地进程。详细故障见[搭建排障](troubleshooting.md)。
