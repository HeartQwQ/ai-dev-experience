# 项目开发规范

使用中文沟通。开发前确认环境、实际需求与锁定版本；新功能按需引入技术，遵守 `mise.toml` / `rust-toolchain.toml` / `pnpm-workspace.yaml` (`catalog:`) 的版本锁定策略。

## 双图谱硬门禁与系统级 Hook 拦截

查询/分析项目业务代码前，`graphify` 和 `codegraph` 必须均已就绪，当前索引有效，且通过双图谱实际查询。仓库 `.agents/hooks.json` 已挂载 `PreToolUse` 与 `Stop` 门禁钩子：

```text
python tools/dev-spec/graph_gate.py build --root .
python tools/dev-spec/graph_gate.py query --root . --question "本次要分析的入口、调用关系或影响范围"
```

图谱失败、过期或缺失时先修复，禁止用纯文本搜索或直接盲读业务代码绕过；图谱结果之后读取真实源码核对。空项目先生成最小官方骨架属于 `BOOTSTRAP`，完成骨架与首次图谱构建后将 `dev-spec.project.json` 的 `phase` 更新为 `READY`。

`graphify` 仅本地代码解析：`GRAPHIFY_BACKEND=none`，禁用云端/LLM；生成 `graphify-out/graph.html`，渲染依赖本地化并通过 SRI/SHA256 校验后再打开。不得上传源码或开启 Cloud/文档语义抽取来绕过限制。

## 契约优先与质量门禁

- **端到端类型契约**：跨端接口以单一 Schema 为唯一事实源（HTTP API 采用 Axum + `utoipa` OpenAPI 3.1 生成前端客户端；Tauri 桌面采用 `tauri-specta` v2 生成类型绑定），禁止手写脱离后端的散落接口类型。
- **前端与全栈检查**：优先使用 Biome (`pnpm check` / `pnpm lint` / `pnpm format`)、`svelte-check`、Vitest Browser Mode 与 Playwright。
- **Rust 检查与供应链**：遵守 Workspace Lints（`unsafe_code = "deny"`），使用 `cargo clippy --all-targets`、`cargo nextest run`（或 `cargo test`）及 `cargo deny check`。
- **一键开发预览**：使用根 `dev.ps1` / `dev.cmd` / `dev.sh` 或 `pnpm dev`。启动脚本通过双栈端口预检与进程组/Job Object 只管理本次拥有的进程；开发数据、凭据与生产严格隔离。
