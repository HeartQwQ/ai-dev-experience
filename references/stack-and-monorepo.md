# 按需技术栈与 monorepo

## 默认选型（2026 前沿基线）

无特殊需求的新项目按下表优先选择；用户要求、交付平台或明确约束可以覆盖。每项需要有实际用途，避免创建项目后安装整个清单。

| 需求 | 优先技术 | 引入边界 |
| --- | --- | --- |
| Web 界面 | SvelteKit (Svelte 5 Runes) + Vite + TypeScript，pnpm (`catalog:`) | 只生成当前需要的 Web 应用；沿官方 `sv` 脚手架，不另套独立 Vite 工程 |
| 样式与通用 UI | Tailwind CSS v4 (`@theme` CSS-first + OKLCH) + shadcn-svelte (Bits UI v2) | 配置别名、语义 token 与所需组件，不安装全部 registry |
| 前端静态检查与格式化 | Biome (`@biomejs/biome`) + `svelte-check` | 默认用 Biome 替代繁琐的 ESLint + Prettier 组合；既有项目沿用原工具链 |
| 请求缓存与服务器状态 | TanStack Svelte Query | 实际存在缓存、失效、乐观更新、重试等需求时 |
| 复杂表格/虚拟化 | 对应 TanStack Svelte 适配模块 | 确认该模块有稳定的 Svelte 5 支持；TanStack 不是一个整体安装包 |
| 复杂动效/时间轴 | GSAP | 简单过渡先使用 CSS / 框架能力；引入后管理卸载清理与 `prefers-reduced-motion` |
| 独立 HTTP 服务 | Rust + Axum + Tokio + `tower-http` + `tracing` (OpenTelemetry) | 没有独立服务需求时不创建无用途后端；错误响应遵循 RFC 9457 Problem Details |
| 跨端类型契约 | HTTP: Axum `utoipa` (OpenAPI 3.1) → `openapi-typescript` / `orval`；桌面: `tauri-specta` v2 | 以后端 Rust 类型为唯一事实源自动生成前端 TS 类型与调用客户端，禁止双端手写漂移 |
| 桌面分发/原生能力 | Tauri v2（严格配置 `capabilities/` 最小权限 ACL） | 不为纯 Web 安装桌面工具链；本地命令足够时不额外启动独立 Axum 服务 |
| 关系数据持久化 | PostgreSQL + `sqlx`（编译期校验或 `.sqlx` 离线元数据） | 没有持久化需求不装库；桌面离线/单机需求先确认选用嵌入式 SQLite 还是远端服务 |
| 工具链与供应链锁定 | `mise.toml` + `rust-toolchain.toml` + `deny.toml` (`cargo-deny`) | 锁定运行时版本、许可证白名单、RustSec 漏洞检查与注册表来源 |

未来标准 UI 库预期边界为 `packages/ui`，独立业务组件、token 和变体；当前只预留目录约定，不伪造已存在库、安装路径或主题。未形成可消费包前，应用使用自己已生成的 shadcn 组件；不要先建立无内容依赖。

## 标准目录

```text
project/
├── apps/
│   ├── web/                 按需：Web SvelteKit (Svelte 5)
│   ├── api/                 按需：Rust/Axum + utoipa
│   └── desktop/             按需：桌面前端与 src-tauri/ (Tauri v2 + tauri-specta)
├── packages/
│   ├── ui/                  有实际共享实现后创建
│   └── contracts/           OpenAPI / Specta 生成的跨端契约与客户端包
├── crates/                  按需：Rust 公共 crate
├── tools/dev-spec/          环境、双图谱门禁、预览与 Hook 门禁脚本
├── .agents/
│   └── hooks.json           PreToolUse 与 Stop 系统级门禁钩子配置
├── infra/                   按需：容器、数据库、迁移与部署配置
├── docs/                    环境记录、启动说明与必要架构决策
├── .dev-spec/local/         本地门禁与日志记录，不提交
├── .gitignore
├── .gitattributes
├── .editorconfig
├── mise.toml                跨语言工具链版本锁定
├── AGENTS.md                项目有效约束与双图谱规则
├── codegraph.json
├── .graphifyignore
├── biome.json               有 JS 应用/包时：极速格式化与 Lint 配置
├── pnpm-workspace.yaml      有 JS 应用/包时（含 catalog: 集中版本表）
├── package.json             有 JS 工具编排时（含 dev/check/lint/format/test/build/graph:*）
├── pnpm-lock.yaml           首次安装后生成并提交
├── rust-toolchain.toml      有 Rust 工程时固定工具链与 rustfmt/clippy
├── deny.toml                有 Rust 工程时配置 cargo-deny 供应链安全基线
├── Cargo.toml               有多个 Rust 成员时建立 workspace 及 [workspace.lints]
└── Cargo.lock               应用工程生成后提交
```

这是一份可裁剪的目标结构，按需求生成对应目录。根编排保持轻量，默认不用 Nx/Turborepo；有缓存/任务图需要再评估。JS 由 pnpm workspace (`catalog:`) 管理，Rust 由 Cargo workspace 管理，运行数据不放应用源码目录。

## 初始化顺序

1. 确认目标是空的新目录或用户明确授权的空仓库，保护父仓库和已有文件。
2. 运行 `python scripts/init_monorepo.py --root 目标目录 --name project-name --components web api --pnpm-version 已解析准确版本 --rust-version 已解析稳定版本`。只有 web/desktop 需要 `--pnpm-version`；可选 `--rust-version` 锁定精确 Rust 版本；可选 `database` 创建基础设施目录。
3. 脚本初始化 Git、写公共配置（含 `.agents/hooks.json`、`mise.toml`、按需 `biome.json`、`rust-toolchain.toml`、`deny.toml`）、复制门禁工具，并创建所选空目录。它不运行网络安装，也不创建假的应用清单或空 Cargo 成员。
4. 在正确目录用实际锁定版本的 Svelte CLI (`sv`)、Cargo/Tauri CLI 生成应用。后端 crate 使用 `cargo init` 等官方命令；有真实成员后再建立根 Cargo workspace，显式写全成员并配置 `[workspace.lints.rust]` (`unsafe_code = "deny"`) 与 `[workspace.lints.clippy]`。
5. SvelteKit 生成时选 TypeScript 与 Svelte 5 Runes；shadcn-svelte 使用匹配版本的 CLI，只加入需要的组件。将共享依赖版本归入 `pnpm-workspace.yaml` 的 `catalog:`。
6. 为数据库选择本地服务或容器方式，补环境样例、`sqlx` 迁移和隔离测试（如 Testcontainers）；没有需求跳过。
7. 编译/构建最小官方骨架后建立双图谱，并将 `dev-spec.project.json` 的 `phase` 更新为 `READY`。进入业务代码分析前必须实际双图谱查询成功。

## 桌面与 Web 的差别及安全边界

Tauri v2 需要目标 OS 的原生依赖，Windows 核对 MSVC/C++ 构建工具、Windows SDK 与 WebView2，macOS 核对 Xcode 工具，Linux 核对 WebKitGTK 等发行版依赖。Rust 后端可在受支持环境构建，不代表能为另一个平台打出原生桌面制品。

桌面 WebView 消费可打包的前端产物，不能把 SvelteKit 的 Node SSR 服务直接当作嵌入页面。按当前 Tauri v2 / SvelteKit 文档配置 `adapter-static` 与 SPA fallback；普通 Web 应用仍可选择 SSR。

**Tauri v2 安全基线**：严格使用 `src-tauri/capabilities/` 定义最小权限（Principle of Least Privilege），按窗口和文件系统/网络作用域（Scope）显式授权，禁止开启通配符全权限或让不可信远程页面访问 `window.__TAURI_INTERNALS__`。

## Git 与可复现性

脚本只初始化仓库，不自动提交或连接远端。忽略依赖、构建、图谱索引、临时数据和真实环境文件；保留 `.env.example`、迁移、`.sqlx/` 离线元数据、图谱配置、锁文件和项目规则。检查 `git check-ignore`，不能只看模板存在。已有仓库不重新初始化、不重写历史。
