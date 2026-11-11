---
name: dev-spec
description: 开发规范。用于项目环境与工程初始化、代码开发和审查，按需应用 Rust/Axum、SvelteKit 5、Tauri v2、PostgreSQL/SQLx、契约驱动开发、UI 设计、工程协作及 Agent/Skill 经验，并执行双图谱代码分析与系统级 Hook 硬门禁。独立语法问答和非开发任务无需使用。
---

# 开发规范

中文显示名为“开发规范”，机器标识为 `dev-spec`（同时提供 `SKILL.md` 与 `plugin.json` / `hooks.json` 双形态挂载）。开发经验按任务读取下列专题；自有 UI 组件标准库与风格尚未实现。

## 按任务使用开发经验

首先遵守用户当前要求、宿主约束和项目有效约定。专题中的通用方法、框架建议、可选预设及历史案例分别按条件使用；项目的已锁版本、当前设计和任务范围优先于经验中的默认建议。引用的外部 Skill 名称仅用于追溯，使用前须确认是否真实可用；不因此自动安装、委派、发布或执行历史命令。

- Rust/Axum、契约驱动、可观测性、数据库迁移与异步服务端：读[后端经验](references/experience/01-后端-Rust-Axum-Tokio.md)，按实际数据库选择 PostgreSQL/SQLx 或 SQLite 章节。
- Svelte 5 / SvelteKit、Runes 状态、契约消费、路由、表单、安全边界与浏览器交互：读[前端经验](references/experience/02-前端-Svelte-SvelteKit.md)，根据部署模式与当前版本判断。
- 界面、OKLCH 视觉体系、容器查询（`@container`）、布局和 WCAG 2.2 无障碍：读 [UI 设计经验](references/experience/05-UI设计.md)；历史视觉预设须按项目需要选择，不当成已实现组件库。
- 工程定位、测试证据、备份、发布和 Git：读[工程与协作](references/experience/04-工程与协作.md)，代码定位受下方双图谱与 `hooks.json` 硬门禁约束。
- 设计或维护 Agent、Skill、Plugin/Hooks、审查及评测：读 [Agent 与 Skill 资产](references/experience/03-Agent与Skill资产.md)，按宿主与用户授权决定是否委派。

完整经验入口及修订记录见[经验目录](references/experience/README.md)。技术版本敏感的经验在使用时核对项目版本与官方资料。

## 开发前的执行顺序

1. **确认环境与项目类型。** 读取目录、规则、清单和锁文件等必要元数据，确认操作系统、CPU、shell、宿主/WSL/容器、工具链、网络/代理、权限、已有 Git 和数据资源。区分新项目与已有项目；已有项目保留选型和锁定版本，不能借搭建环境重构或升级全仓。详情读[环境确认](references/environment.md)。
2. **按需求选择前沿技术栈组件。** 新项目无特殊要求时，Web 优先 SvelteKit (Svelte 5 Runes) + Vite + Tailwind CSS v4 + shadcn-svelte，包管理用 pnpm（配合 `catalog:` 统一锁版本），静态检查与格式化优先 Biome；数据缓存/表格选对应 TanStack 模块，复杂动效才加 GSAP；服务端优先 Rust + Axum + Tokio + `tracing`/OpenTelemetry；跨端契约优先 `utoipa` (OpenAPI 3.1) 或 `tauri-specta` v2；桌面优先 Tauri v2（严格 Capabilities ACL）；关系数据库优先 PostgreSQL + `sqlx`。只引入这次需要的模块。详情读[选型与工程](references/stack-and-monorepo.md)。
3. **安装需要的环境并固定版本。** 首次安装时查官方稳定渠道，排除 alpha/beta/RC/nightly/yanked，检查 engine/peer/平台兼容；安装兼容的最新稳定版本并记录理由和解析时间。通过 `mise.toml`、`rust-toolchain.toml`、`pnpm-workspace.yaml` (`catalog:`) 与锁文件保证跨机器可复现，日常开发不持续追 `latest`。
4. **建立 monorepo 与 Git。** 新项目建立根编排与按需应用/公共包目录，初始化 Git、忽略与行尾规则；锁文件保留入库。先用 `scripts/init_monorepo.py` 建立空骨架（含 `.agents/hooks.json`、`mise.toml`、按需 `biome.json` / `rust-toolchain.toml` / `deny.toml`），再使用官方 CLI 生成所选工程；骨架脚本不声称已创建可运行的 Svelte/Rust 应用。
5. **配置本地双图谱并通过硬门禁。** 读取[图谱门禁](references/graph-gate.md)，安装并配置 `graphify`（包名 `graphifyy`）、`codegraph`，建立本项目索引。`graphify` 必须本地代码解析、禁用云端/LLM，生成原生 `graph.html` 并将渲染依赖本地化且校验 SRI/SHA256。图谱工具及索引未就绪时停在修复环境阶段，禁止纯文本搜索代替代码分析。查询项目代码时必须实际使用图谱工具分析，再读真实源码核对。
6. **配置开发/生产、测试与一键预览。** 根据[环境与测试](references/dev-prod-and-tests.md)配置变量、数据、启动、检查和 CI，提供根 `dev.ps1` / `dev.cmd` / `dev.sh` 及 JS 工程的 `pnpm dev`；实际启动所需服务（通过双栈端口预检与日志自动摘要诊断），打开开发页面与本地网状图，退出时清理自己创建的进程树。遇到问题读[搭建排障](references/troubleshooting.md)。

## 图谱与 Hook 硬门禁

- 两个工具均必须安装并可执行；当前项目的两份索引均建立且有效。正常代码查询使用 `scripts/graph_gate.py query --root 项目根目录 --question 问题`，该入口实际调用两个图谱；成功后再查看命中源码与调用方。
- 更改源文件、清单、忽略或图谱配置，切换分支或工具版本后，重新检查并刷新索引。不得用“已有图谱文件”冒充当前索引有效。失败、空结果和不支持语言按参考处理，不能记成已分析。
- 空项目允许先生成最小官方骨架，以便建立首份索引；该阶段标为 `BOOTSTRAP`，完成骨架与首次图谱构建后将 `dev-spec.project.json` 中的 `phase` 更新为 `READY`。阅读环境元数据、图谱诊断和安装帮助不属于绕过门禁查业务代码。
- 本包同时提供 `scripts/hook_gate.py` 与 `.agents/hooks.json`（及插件根 `hooks.json`），在支持生命周期钩子的宿主中自动拦截 `PreToolUse`（未完成有效双图谱构建与查询时拒绝业务代码检索/读取）与 `Stop`（检查未清理的后台预览守护进程）。

## 使用脚本与交付

脚本路径相对本 Skill：`scripts/environment.py` 探测必需与推荐工具链；`scripts/init_monorepo.py` 创建新目录骨架、工程基线配置并初始化 Git；`scripts/graph_gate.py` 构建、校验、双图谱查询和本地化离线图；`scripts/dev.py` 监督一键预览与自动日志尾部诊断；`scripts/hook_gate.py` 执行 `PreToolUse` / `Stop` 系统级门禁。运行前读取对应参考中的参数，使用实际 Python 解释器路径。

完成后报告所选/未引入组件、安装和锁定版本、工程入口、两份图谱及查询证据、已执行检查、未通过项。开发、测试、生产的结果分别说明；没有安装、连接或运行的能力不得称为就绪。官方来源见[资料索引](references/sources.md)。
