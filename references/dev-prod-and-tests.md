# 开发、生产、测试与一键预览

## 配置与数据隔离

区分 `development`、`test` 与 `production`。真实值放各环境受控配置或秘密管理中；仓库只保留变量名、用途、必填/默认、读取阶段和无秘密样例。前端公开变量视为可见内容，不能存数据库密码、服务凭据或签名材料。

每个应用记录自己读取哪些变量，谁负责注入；SvelteKit/Vite 的公开前缀和构建/运行阶段按实际版本核对。桌面安装包中的配置也不是秘密存储。生产制品固定构建标识，不能用开发代理的隐式配置替代生产接线。

开发、测试、生产分别使用数据库/账号、数据目录、上传目录和端口。开发预览不使用生产数据写入权限。PostgreSQL 明确服务与数据库版本、连接池/超时（含 `statement_timeout`）、`sqlx` 迁移入口、在线无锁演进（Expand-Contract）、备份/恢复、TLS 和最小所需权限；这些项在选用数据库后执行，不先安装无用途服务。

`.env.example` 可提交，真实 `.env`、`.env.development.local` 等忽略。根预览器只支持简单 `KEY=value`，不执行 shell 替换或插值；复杂 env 格式由实际运行框架管理，并调整明确的启动命令。日志不打印变量值和凭据。

## 一键开发预览

新工程提供 `dev.ps1`、Windows 可双击的 `dev.cmd`、POSIX `dev.sh` 和 JS workspace 的 `pnpm dev`。调用方可设置 `DEV_SPEC_PYTHON`，否则使用初始化时本地记录的 Python 路径，跨机器找不到时回退系统解释器。克隆后重新做环境确认，不提交机器绝对路径。

```text
pnpm dev
python tools/dev-spec/dev.py --root .
python tools/dev-spec/dev.py --root . --check-only
python tools/dev-spec/dev.py --root . --no-browser
```

`--check-only` 只检查配置与必要路径/双栈端口，不证明图谱或运行通过。普通启动按以下顺序：

1. 读取根 `dev-spec.project.json`，确认实际应用文件、命令和本地就绪地址；读取开发 env。
2. **双栈端口预检**：同时检查 IPv4 (`127.0.0.1`) 与 IPv6 (`::1`) 上的目标端口占用，冲突即报告占用主机与端口，不能杀掉未知进程或悄悄换端口。
3. 校验双图谱；过期时重新本地构建/导出，执行实际双图谱启动路径查询。
4. 按服务列表启动所需 API、Web 或桌面进程（自动将上次非空日志轮转为 `{name}.prev.log`，上限 5 MiB）并等待声明的就绪条件。缺少应用、依赖或健康接口，或进程异常退出/超时时，**自动截取对应服务日志尾部 30 行直接输出到错误摘要**。
5. 打开本地 Web 预览 URL（有 Web/API 时）；另起只绑定 `127.0.0.1`、只服务 `graphify-out` 目录的本地图查看器，打开原生 `graph.html`。图查看器使用 OS 分配的空闲端口并打印实际地址；应用约定端口仍严格检查。Tauri 窗口由其开发命令启动。
6. 写入 `.dev-spec/local/dev-supervisor.pid` 并保持监督；某服务异常退出时打印该服务日志尾部并停止本次其他进程。Ctrl+C 逆序清理拥有的进程树并移除 PID 文件，不影响启动前已有服务。

首次骨架没有真实应用：先用官方 CLI 生成应用、补准确 dev 脚本/监听配置/健康接口和前端 API 地址，再运行预览。默认 API 示例要求应用读取 `API_HOST`/`API_PORT` 并提供 `/health`，这些不是脚本凭空生成的功能。配置中的命令以参数数组执行，不拼接 shell 字符串。

若需要自动拉起开发 PostgreSQL，将仅供开发的 Docker Compose/服务命令和健康等待明确加入启动顺序。不得自动初始化、迁移或清理任意已有数据库；停机与数据删除不能混成预览退出动作。外部已管理的数据库只做连接验收。

脚本在 Windows 将创建的服务分配到本次拥有的 64 位安全句柄 Job Object（`JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`），关闭时清理该树；无法建立隔离时拒绝启动。在 POSIX 使用创建的新进程组。退出时同时关闭本地图 HTTP 查看器。桌面进程仍存活只表示已启动，不证明窗口和 IPC 全部可用。

## 测试与质量工具按需求引入（2026 标准）

| 层级 | 优先工具/做法 | 最小有效验收 |
| --- | --- | --- |
| 前端静态与格式化 | TypeScript、`svelte-check`、Biome (`biome check`) | 项目脚本真实存在并通过，不用空命令顶替 |
| 跨端契约校验 | `utoipa` OpenAPI 导出比对 / `tauri-specta` 绑定生成检查 | 后端 schema 变更与前端生成类型零漂移 |
| 前端逻辑/组件 | Vitest + **Vitest Browser Mode (Playwright Provider)** / `vitest-browser-svelte` | 在真实无头浏览器中验证 Svelte 5 Runes 状态、真实布局、焦点与交互断言 |
| Web 用户流程 | Playwright（含 `@axe-core/playwright` 基线扫描） | 关键流程、浏览器和代表性视口按产品需要 |
| Rust 静态与供应链 | `rustfmt`、`clippy --all-targets`、`cargo check`、`cargo deny check` | 受支持目标与特性组合，遵守 `[workspace.lints]`（如 `unsafe_code = "deny"`）及许可证/漏洞门禁 |
| Rust 单元/接口 | `cargo nextest run`（或 `cargo test`）、Tower `oneshot` 服务测试 | 请求/响应、RFC 9457 错误结构、权限和失败路径 |
| PostgreSQL 集成 | Testcontainers / 隔离测试库、`sqlx` 迁移与编译期检查 | 空库迁移、Expand-Contract 兼容、关键读写和回滚边界 |
| Tauri v2 | Rust 命令测试、前端测试、`capabilities/` 权限校验与目标平台打包 | native bridge、最小权限 ACL、启动和真实打包 |
| 图谱、Hook 与预览 | 两份索引、真实查询、网状图、`hook_gate.py --self-test` 和服务就绪 | 正常路径及过期/失败阻断 |

测试工具也遵守首次最新稳定兼容、之后锁定的策略。不因技术栈列出工具就全部装入；纯后端不安装浏览器与前端测试运行时，原生桌面没有 Web 等价能力时不能假装用浏览器证明。

## CI 与生产检查

应用产生实际实现后，为根命令配置真实聚合：安装冻结锁文件（`pnpm install --frozen-lockfile`）、格式/静态（`pnpm lint` / `pnpm check` / `cargo clippy` / `cargo deny check`）、相关测试（`pnpm test` / `cargo nextest run`）、所选应用构建。图谱门禁应在需要代码分析的代理/流水线步骤之前执行。

Linux CI 不证明 Windows/macOS Tauri 可打包；按目标系统设置构建矩阵。容器/生产部署的配置、制品、就绪、日志（OTLP / 结构化 JSON）和回滚单独验证。生产启动使用已构建制品，不能把 Vite dev server 当生产服务。

验收记录分为通过、失败、受阻、未执行、不适用。模拟响应只证明相应界面分支，真实认证/存储/部署需要各自证据。环境搭建完成时至少跑所选骨架的类型/编译、最小测试、构建、双图谱查询及实际预览；未执行项明确保留。
