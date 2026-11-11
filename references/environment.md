# 环境确认与版本策略

## 环境清单

开发前确认项目根路径、新建/接手、目标产品（Web/API/桌面）、部署目标与已有约束。元数据探测允许目录列表、清单/锁文件、Git 状态和工具帮助；业务代码的定位分析进入图谱门禁。

执行 `python scripts/environment.py --root 项目根目录 --features web api database`；按实际需求传 `web`、`api`、`desktop`、`database`，不需要的能力不检测为必需。输出不包含环境变量值或凭据，且不会自动安装软件。

核对：

- OS、架构、当前 shell、实际解释器与 PATH；区分原生 Windows、WSL、容器及其文件系统。
- 必需工具：`git`、`graphify`、`codegraph`；按需确认 `node`/`pnpm`、`rustup`/`rustc`/`cargo`（含 `rustfmt` 与 `clippy` 组件）、PostgreSQL 客户端（`psql`）或容器（`docker`），桌面还确认原生构建依赖。
- 推荐现代工程工具：`uv`、`mise`（跨语言运行时锁定）、`biome`（前端极速检查与格式化）、`cargo-nextest`（Rust 并行隔离测试）、`cargo-deny`（Rust 依赖许可证与安全漏洞审计）、`sqlx`（SQLx CLI 迁移与离线元数据）。
- 管理员权限是否必要，依赖下载网络/代理/证书，包源及镜像来源；离线缓存是否满足实际版本。
- 现有监听端口（IPv4 `127.0.0.1` 与 IPv6 `::1` 双栈）、进程归属、数据库实例/数据目录、磁盘空间、内存及文件监视能力。探测脚本不替代平台原生前置条件检查。
- 项目实际版本、子工程入口、CI、设计系统与迁移约束。只改当前项目需要的配置。

## 最新稳定版本与可复现锁定

**新项目首次选定组件时解析最新稳定版本；选定后固定并复现。** 优先官方发布页与对应 registry。npm 的 `latest`、PyPI 的版本元数据、Rust stable、PostgreSQL 正式支持版本需要核对，不能把 tag 名当作已完成兼容检查。

1. 获取候选正式版本，排除预发布、nightly、撤回或失效版本。
2. 检查 Node engine、peerDependencies、Svelte 5 / 组件库、Tailwind CSS v4、Tauri v2 CLI/API/Rust crate、数据库客户端/服务器和 OS/CPU 兼容。
3. 安装需要的候选并跑最小验证。若最新候选不兼容，使用最新的兼容稳定版本，记录阻塞因素和选择理由，不悄悄放宽版本要求。
4. 记录准确版本、来源、解析时间、工具路径和验证状态。Node 的 latest stable 与 latest LTS 分别确认；默认选满足支持矩阵的稳定线，选择 LTS 的原因写清，不把 LTS 名称等同最新发行。
5. **多层锁定机制**：
   - 根 `mise.toml` 固定已解析的 `node`、`pnpm`、`rust` 等运行时版本。
   - 根 `package.json` 固定 pnpm 的 `packageManager`，并在 `pnpm-workspace.yaml` 的 `catalog:` 中集中管理跨子包共享依赖版本。
   - Rust 用项目级 `rust-toolchain.toml` 固定已验证 stable 版本（如 `1.85.0`）与 `["rustfmt", "clippy"]` 组件，并用 `deny.toml` 锁定供应链策略。
   - 数据库镜像/软件包固定精确主次版本，不使用浮动 `latest` 上生产。

版本核对命令示例（只查已选择组件）：

```text
pnpm view @sveltejs/kit dist-tags engines peerDependencies --json
pnpm view vite dist-tags engines peerDependencies --json
pnpm view tailwindcss dist-tags engines peerDependencies --json
pnpm view shadcn-svelte dist-tags engines peerDependencies --json
pnpm view @biomejs/biome dist-tags engines --json
pnpm view @colbymchenry/codegraph dist-tags engines --json
uv tool install graphifyy
rustup show
rustc --version --verbose
```

安装命令与版本查询分别处理。`graphify` 用 `uv` 隔离工具环境；按解析版本安装时将版本号写入命令。既有项目使用锁定版本，升级是独立变更；网络不可用时明确最新版本尚未核对。

## 安装后的复核

工具 `--version` 成功只是第一层。还需验证实际编译/构建、数据库连接与迁移、浏览器或桌面运行、两份图谱构建/查询及 `.agents/hooks.json` 门禁连通性。记录失败原文与对应层级。进程重启或新终端可能才看到更新 PATH，不能继续调用旧解释器却宣称已更新。
