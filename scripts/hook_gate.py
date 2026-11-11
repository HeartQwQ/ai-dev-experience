"""Lifecycle hook gate for Antigravity / agent hosts (hooks.json PreToolUse & Stop)."""
import argparse
import json
from pathlib import Path
import re
import sys

METADATA_FILENAMES = {
    "package.json", "pnpm-lock.yaml", "pnpm-workspace.yaml", "Cargo.toml", "Cargo.lock",
    "rust-toolchain.toml", "deny.toml", "biome.json", "biome.jsonc", "mise.toml",
    "tsconfig.json", "svelte.config.js", "vite.config.ts", "vite.config.js",
    "components.json", "codegraph.json", "dev-spec.project.json", "AGENTS.md",
    "GEMINI.md", "README.md", ".gitignore", ".gitattributes", ".editorconfig",
    ".graphifyignore", ".env.example", "hooks.json", "plugin.json", "SKILL.md",
}
BUSINESS_DIRS = {"apps", "packages", "crates", "src", "src-tauri"}
SEARCH_TOOLS = {"grep_search", "find_by_name", "codebase_search", "search_files", "ripgrep"}
READ_TOOLS = {"read_file", "view_file", "view_file_outline", "view_code_item"}
CMD_TOOLS = {"run_command", "bash", "execute_command", "shell"}
SEARCH_CMD_RE = re.compile(
    r"(?:^|[;&|]\s*)(?:rg|grep|egrep|fgrep|findstr|Select-String)\b",
    re.IGNORECASE,
)
SAFE_CMD_RE = re.compile(
    r"(?:graph_gate\.py|environment\.py|init_monorepo\.py|dev\.py|hook_gate\.py|"
    r"graphify\b|codegraph\b)",
    re.IGNORECASE,
)


def resolve_root(cli_root, payload):
    if cli_root:
        return Path(cli_root).resolve()
    workspaces = payload.get("workspacePaths") or []
    if workspaces and isinstance(workspaces[0], str):
        return Path(workspaces[0]).resolve()
    cwd = Path.cwd().resolve()
    if cwd.name in {".agents", ".agent"} and (cwd.parent / "dev-spec.project.json").is_file():
        return cwd.parent
    return cwd


def is_dev_spec_project(root):
    return (root / "dev-spec.project.json").is_file() or (root / ".dev-spec").is_dir()


def is_bootstrap_phase(root):
    config_path = root / "dev-spec.project.json"
    if not config_path.is_file():
        return False
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
        return data.get("phase") == "BOOTSTRAP"
    except (OSError, ValueError):
        return False


def verify_dual_graph_ready(root):
    state_file = root / ".dev-spec" / "local" / "graph-state.json"
    query_file = root / ".dev-spec" / "local" / "last-query.json"
    if not state_file.is_file() or not query_file.is_file():
        return False, "缺少双图谱状态或查询记录（需先执行 graph_gate.py build 与 query）"
    try:
        state = json.loads(state_file.read_text(encoding="utf-8"))
        last_query = json.loads(query_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False, "双图谱状态文件损坏，请重新运行 graph_gate.py build 与 query"

    if not state.get("local_only"):
        return False, "图谱未处于纯本地模式（local_only != true）"
    if state.get("source") != last_query.get("source"):
        return False, "源码指纹已变更，上次双图谱查询记录已过期，请重新执行 graph_gate.py query"

    graph_json = root / "graphify-out" / "graph.json"
    graph_html = root / "graphify-out" / "graph.html"
    codegraph_db = root / state.get("codegraph_index", ".codegraph/codegraph.db")
    for artifact in (graph_json, graph_html, codegraph_db):
        if not artifact.is_file() or artifact.stat().st_size == 0:
            return False, f"缺少必需图谱产物：{artifact.name}"
    return True, "ok"


def is_business_source_path(root, raw_path):
    if not raw_path or not isinstance(raw_path, str):
        return False
    try:
        target = Path(raw_path).resolve()
        rel = target.relative_to(root)
    except (OSError, ValueError):
        return False
    if not rel.parts:
        return False
    if rel.name in METADATA_FILENAMES or rel.name.startswith(".env"):
        return False
    if rel.parts[0] in {"tools", "docs", ".agents", ".dev-spec", "infra", "graphify-out", ".codegraph"}:
        return False
    return rel.parts[0] in BUSINESS_DIRS


def handle_pre_tool_use(root, payload):
    if not is_dev_spec_project(root) or is_bootstrap_phase(root):
        return {"decision": "allow"}

    tool_call = payload.get("toolCall") or {}
    tool_name = str(tool_call.get("name") or "").lower()
    args = tool_call.get("args") or {}

    needs_gate = False
    if tool_name in SEARCH_TOOLS:
        search_path = args.get("SearchPath") or args.get("SearchDirectory") or args.get("path") or str(root)
        try:
            resolved = Path(search_path).resolve()
            if resolved == root or resolved.is_relative_to(root):
                needs_gate = True
        except (OSError, ValueError):
            pass
    elif tool_name in READ_TOOLS:
        target_path = args.get("Path") or args.get("AbsolutePath") or args.get("File") or args.get("path")
        if is_business_source_path(root, target_path):
            needs_gate = True
    elif tool_name in CMD_TOOLS:
        cmd_line = str(args.get("CommandLine") or args.get("command") or "")
        if SEARCH_CMD_RE.search(cmd_line) and not SAFE_CMD_RE.search(cmd_line):
            needs_gate = True

    if not needs_gate:
        return {"decision": "allow"}

    ready, reason = verify_dual_graph_ready(root)
    if ready:
        return {"decision": "allow"}
    return {
        "decision": "deny",
        "reason": (
            f"[dev-spec 双图谱硬门禁拦截] {reason}。"
            "禁止退化为纯文本搜索或直接盲读业务源码；请先运行 "
            "`python tools/dev-spec/graph_gate.py build --root .` 与 "
            "`python tools/dev-spec/graph_gate.py query --root . --question \"...\"`。"
        ),
    }


def handle_stop(root, payload):
    if not is_dev_spec_project(root):
        return {"decision": "allow"}
    reason = str(payload.get("terminationReason") or "")
    if reason != "NO_TOOL_CALL":
        return {"decision": "allow"}
    pid_file = root / ".dev-spec" / "local" / "dev-supervisor.pid"
    if pid_file.is_file():
        return {
            "decision": "continue",
            "reason": (
                "[dev-spec 进程清理门禁] 检测到 `.dev-spec/local/dev-supervisor.pid` 仍存在，"
                "说明一键预览守护进程尚未退出。请先停止本次拥有的后台预览进程后再结束任务。"
            ),
        }
    return {"decision": "allow"}


def self_test():
    sample_allow = handle_pre_tool_use(Path.cwd(), {"toolCall": {"name": "read_file", "args": {"Path": "README.md"}}})
    assert sample_allow["decision"] == "allow", f"Unexpected self-test result: {sample_allow}"
    return {"status": "passed", "self_test": sample_allow}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event", choices=["pre-tool-use", "stop"], default="pre-tool-use")
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        print(json.dumps(self_test(), ensure_ascii=False))
        return 0

    raw_input = sys.stdin.read().strip()
    payload = {}
    if raw_input:
        try:
            payload = json.loads(raw_input)
        except ValueError:
            payload = {}

    root = resolve_root(args.root, payload)
    if args.event == "stop":
        response = handle_stop(root, payload)
    else:
        response = handle_pre_tool_use(root, payload)

    print(json.dumps(response, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
