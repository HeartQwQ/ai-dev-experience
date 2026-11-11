# 来源与核对范围

核对日期：2026-11-11。以下用于版本/能力依据，实际初始化时仍需获取最新稳定且兼容的发布，不把本页当版本锁。

- **插件、Skill 与 Lifecycle Hooks 规范**：Antigravity Customization System（`SKILL.md`、`plugin.json`、`hooks.json` 的 `PreToolUse`/`Stop` 协议）及 [OpenAI 插件规范](https://developers.openai.com/plugins/build/plugins)。机器标识使用 `dev-spec`，中文显示名使用“开发规范”。
- **graphify 安装、CLI/助手/MCP 区别与本地模式**：[官方仓库](https://github.com/Graphify-Labs/graphify)、[CLI](https://docs.graphify.com/reference/overview)、[本地抽取](https://docs.graphify.com/reference/extract)。核对 pyproject、CLI 与 HTML 导出源码；不复制上游 Skill 正文。
- **codegraph 安装、初始化、CLI 与配置**：[官方仓库](https://github.com/colbymchenry/codegraph)。同时核对 `package.json` 和 CLI 初始化参数；其自动同步描述不能替代本插件新鲜度检查。
- **Svelte 5 & SvelteKit CLI**：[官方 CLI 入口](https://svelte.dev/docs/cli/overview)、[Svelte 5 Runes 文档](https://svelte.dev/docs/svelte/what-are-runes)。具体脚手架参数以当前 `sv --help` 为准。
- **Tailwind CSS v4 & shadcn-svelte**：[Tailwind v4 CSS-first 配置](https://tailwindcss.com/docs/functions-and-directives)、[shadcn-svelte SvelteKit 安装](https://www.shadcn-svelte.com/docs/installation/sveltekit)。
- **Biome & Vitest Browser Mode**：[Biome 官方文档](https://biomejs.dev/guides/getting-started/)、[Vitest Browser Mode](https://vitest.dev/guide/browser/)。
- **TanStack & GSAP**：[TanStack Svelte Query](https://tanstack.com/query/latest/docs/framework/svelte/overview)、[GSAP 官方安装](https://gsap.com/docs/v3/Installation/)。
- **pnpm & mise**：[pnpm Workspaces & Catalogs (`catalog:`)](https://pnpm.io/catalogs)、[mise-en-place 工具链版本管理](https://mise.jdx.dev/)。
- **Rust、Axum、契约与供应链工具**：[Rust 稳定工具链](https://www.rust-lang.org/tools/install)、[Axum 文档](https://docs.rs/axum/latest/axum/)、[utoipa OpenAPI 3.1](https://docs.rs/utoipa/latest/utoipa/)、[RFC 9457 Problem Details](https://www.rfc-editor.org/rfc/rfc9457.html)、[cargo-nextest](https://nexte.st/)、[cargo-deny](https://embarkstudios.github.io/cargo-deny/)。
- **Tauri v2 & Specta**：[Tauri v2 平台前置依赖](https://v2.tauri.app/start/prerequisites/)、[Tauri v2 Capabilities 与权限最小化](https://v2.tauri.app/security/capabilities/)、[tauri-specta](https://github.com/oscartbeaumont/tauri-specta)。
- **PostgreSQL & SQLx**：[PostgreSQL 正式支持策略](https://www.postgresql.org/support/versioning/)、[SQLx 编译期校验与迁移](https://github.com/launchbadge/sqlx)。

这些来源支持工具接口和兼容边界；按需选型、契约驱动、双图谱与 Hook 硬门禁、monorepo、本地图和一键预览是本规范的核心要求。
