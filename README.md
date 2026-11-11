# dev-spec · 可复用 AI 开发经验与开发规范

面向 AI 辅助开发的一套中文工程规范与经验库：从环境确认、按需选型、版本锁定、monorepo 骨架，到双图谱代码分析门禁、开发/测试/生产隔离与一键预览。

机器标识 `dev-spec`，中文显示名「开发规范」。同时提供 Skill 形态（`SKILL.md`）与 Plugin / Lifecycle Hooks 形态（`plugin.json`、`hooks.json`）。

## 内容导航

| 路径 | 内容 |
| --- | --- |
| `SKILL.md` | 开发前六步执行顺序、双图谱门禁、Hook 规则与交付要求 |
| `references/experience/` | 5 篇可复用经验：后端 Rust/Axum、前端 Svelte/SvelteKit、Agent 与 Skill 资产、工程与协作、UI 设计；另有总览、修订说明与核对记录 |
| `references/` | 环境确认、技术栈与 monorepo、图谱门禁、开发/生产/测试、搭建排障、官方来源索引 |
| `scripts/` | 5 个 Python 脚本：环境探测、骨架初始化、图谱门禁、一键预览监督、Hook 门禁 |
| `assets/monorepo/` | 新项目模板：AGENTS.md、忽略与行尾规则、`dev.ps1` / `dev.cmd` / `dev.sh` / `dev.mjs` |
| `agents/openai.yaml` | 显示名与简述 |

## 三条核心规则

1. **按需与锁定**：只有新项目才解析最新稳定版本，并通过 `mise.toml`、`pnpm-workspace.yaml` 的 `catalog:`、`rust-toolchain.toml`、`deny.toml` 多层锁定；已有项目保留既有选型和锁定版本，不借搭建环境重构全仓。只引入本次真正需要的组件。
2. **双图谱硬门禁**：`graphify`（包名 `graphifyy`）与 `codegraph` 必须本地安装、建立当前项目索引并实际查询，随后再读命中源码核对。禁止用纯文本搜索代替图谱分析；失败不降级、不开云端或 LLM 后端（固定 `GRAPHIFY_BACKEND=none`、`--code-only`）；`graph.html` 的 CDN 渲染依赖须本地化并校验 SRI/SHA256。
3. **系统级 Hook 拦截**：项目处于 `READY` 阶段时，`PreToolUse` 拒绝未完成图谱门禁的业务源码检索与读取，`Stop` 检查残留的预览守护进程；空项目先走 `BOOTSTRAP`，生成最小官方骨架与首份索引后再切到 `READY`。

配套约束还包括契约优先（HTTP 用 `utoipa` OpenAPI 3.1、桌面用 `tauri-specta` v2，禁止双端手写类型漂移）、Tauri v2 Capabilities 最小权限、IPv4/IPv6 双栈端口预检、Windows Job Object / POSIX 进程组清理，以及开发、测试、生产数据与凭据的严格隔离。

## 技术栈基线（2026 核对）

SvelteKit + Svelte 5 Runes / Tailwind CSS v4 / shadcn-svelte / Biome / pnpm；Rust + Axum + Tokio / `utoipa` / `sqlx`；Tauri v2；Vitest Browser Mode / Playwright / `cargo-nextest` / `cargo-deny`。官方文档链接与核对范围见 `references/sources.md`（核对日期 2026-11-11）。该页不作为版本锁，实际使用仍需按项目锁定版本核对。

## 使用前注意

- 脚本依赖 Python 与 `uv`；图谱门禁还需要 `graphify` 和 `codegraph` 两个 CLI，缺一即阻断业务代码分析。
- 经验库区分「通用方法 / 技术栈专项 / 项目约定 / 历史案例」四层。历史案例缺少环境与复现记录，不能当作现测结果或容量保证；整套资料也不是已有项目的强制重构清单。
- `references/experience/修订说明.md` 记录 R01–R38 的修改去向，`文档核对记录.json` 是文档结构与脚本自检结果。
- 本仓库仅含规范、经验文档、脚本与模板，不含凭据、模型权重、运行环境数据或任何业务项目源码。

## 来源

整理自本地 `dev-spec` Skill 的完整分发包，公开时排除了 Python 编译缓存。经验条目由既有项目实践与现代行业规范归纳，版本敏感内容请对照官方资料与项目实际锁定版本。
