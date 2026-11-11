"""Create an empty monorepo skeleton without installing frameworks or dependencies."""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys


BIOME_CONFIG = {
    "$schema": "https://biomejs.dev/schemas/stable/schema.json",
    "vcs": {"enabled": True, "clientKind": "git", "useIgnoreFile": True},
    "files": {
        "ignoreUnknown": True,
        "ignore": [
            "node_modules",
            "dist",
            "build",
            ".svelte-kit",
            "target",
            "graphify-out",
            ".codegraph",
            ".dev-spec",
            "coverage",
            "playwright-report",
        ],
    },
    "formatter": {"enabled": True, "indentStyle": "space", "indentWidth": 2, "lineEnding": "lf"},
    "linter": {"enabled": True, "rules": {"recommended": True}},
    "overrides": [
        {
            "include": ["*.svelte"],
            "linter": {
                "rules": {
                    "style": {"useConst": "off", "useImportType": "off"},
                    "correctness": {"noUnusedVariables": "off", "noUnusedImports": "off"},
                }
            },
        }
    ],
}

PROJECT_HOOKS_CONFIG = {
    "dev-spec-graph-gate": {
        "enabled": True,
        "PreToolUse": [
            {
                "matcher": "grep_search|find_by_name|read_file|view_file|view_file_outline|view_code_item|run_command",
                "hooks": [
                    {
                        "type": "command",
                        "command": "uv run --no-project python ../tools/dev-spec/hook_gate.py --event pre-tool-use",
                        "timeout": 10,
                    }
                ],
            }
        ],
        "Stop": [
            {
                "type": "command",
                "command": "uv run --no-project python ../tools/dev-spec/hook_gate.py --event stop",
                "timeout": 10,
            }
        ],
    }
}

CARGO_DENY_TEMPLATE = """# cargo-deny configuration baseline (https://embarkstudios.github.io/cargo-deny/)
[advisories]
ignore = []

[licenses]
allow = [
  "MIT",
  "Apache-2.0",
  "Apache-2.0 WITH LLVM-exception",
  "BSD-2-Clause",
  "BSD-3-Clause",
  "ISC",
  "Unicode-3.0",
  "Unicode-DFS-2016",
  "Zlib",
]

[bans]
multiple-versions = "warn"
wildcards = "deny"

[sources]
unknown-registry = "deny"
unknown-git = "deny"
allow-registry = ["https://github.com/rust-lang/crates.io-index"]
"""


def initialize(root, name, components, pnpm_version=None, rust_version=None):
    root = root.resolve()
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", name):
        raise ValueError("Use a lowercase project identifier")
    comp_set = set(components)
    javascript = bool(comp_set & {"web", "desktop"})
    rust = bool(comp_set & {"api", "desktop"})
    if javascript and not (pnpm_version and re.fullmatch(r"\d+\.\d+\.\d+", pnpm_version)):
        raise ValueError("Resolve an exact stable pnpm version before creating a JS workspace")
    if rust_version and not re.fullmatch(r"(?:stable|\d+\.\d+\.\d+)", rust_version):
        raise ValueError("Use 'stable' or an exact stable Rust version (e.g. 1.85.0)")
    if root.is_symlink() or (root.exists() and any(p.name != ".git" for p in root.iterdir())):
        raise ValueError("Target must be new/empty, or contain only its existing .git directory")
    git = shutil.which("git")
    if not git:
        raise ValueError("Git is required")
    ancestor = root
    while not ancestor.exists():
        ancestor = ancestor.parent
    parent_git = subprocess.run(
        [git, "-C", str(ancestor), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
    )
    if parent_git.returncode == 0 and Path(parent_git.stdout.strip()).resolve() != root:
        raise ValueError("Target is inside an existing repository; use that monorepo root instead")

    skill = Path(__file__).resolve().parents[1]
    templates = skill / "assets" / "monorepo"
    planned = {p.name: p.read_bytes() for p in templates.iterdir() if p.is_file()}
    for script in ("environment.py", "graph_gate.py", "dev.py", "hook_gate.py"):
        planned[f"tools/dev-spec/{script}"] = (skill / "scripts" / script).read_bytes()
    planned[".agents/hooks.json"] = (
        json.dumps(PROJECT_HOOKS_CONFIG, ensure_ascii=False, indent=2) + "\n"
    ).encode("utf-8")

    mise_lines = [
        "# Pin resolved stable runtime versions here for reproducible environments",
        "[tools]",
    ]
    if javascript:
        mise_lines.append(f'pnpm = "{pnpm_version}"')
    if rust:
        mise_lines.append(f'rust = "{rust_version or "stable"}"')
    planned["mise.toml"] = ("\n".join(mise_lines) + "\n").encode("utf-8")

    services = []
    if "api" in comp_set:
        services.append(
            {
                "name": "api",
                "command": ["cargo", "run", "--manifest-path", "apps/api/Cargo.toml"],
                "required_paths": ["apps/api/Cargo.toml"],
                "env": {"API_HOST": "127.0.0.1", "API_PORT": "3000"},
                "ready_url": "http://127.0.0.1:3000/health",
                "timeout_seconds": 180,
            }
        )
    if "web" in comp_set:
        services.append(
            {
                "name": "web",
                "command": [
                    "pnpm",
                    "--dir",
                    "apps/web",
                    "dev",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    "5173",
                    "--strictPort",
                ],
                "required_paths": ["apps/web/package.json"],
                "env": {},
                "ready_url": "http://127.0.0.1:5173",
                "timeout_seconds": 120,
            }
        )
    if "desktop" in comp_set:
        services.append(
            {
                "name": "desktop",
                "command": ["pnpm", "--dir", "apps/desktop", "tauri", "dev"],
                "required_paths": ["apps/desktop/package.json", "apps/desktop/src-tauri/Cargo.toml"],
                "env": {},
                "ready_url": None,
                "timeout_seconds": 180,
            }
        )
    config = {
        "schema_version": 1,
        "phase": "BOOTSTRAP",
        "components": components,
        "preview_url": "http://127.0.0.1:5173"
        if "web" in comp_set
        else ("http://127.0.0.1:3000/health" if "api" in comp_set else None),
        "services": services,
        "graph_question": "application entry routes service startup",
    }
    planned["dev-spec.project.json"] = (
        json.dumps(config, ensure_ascii=False, indent=2) + "\n"
    ).encode("utf-8")

    if javascript:
        package = {
            "name": name,
            "private": True,
            "packageManager": "pnpm@" + pnpm_version,
            "scripts": {
                "dev": "node dev.mjs",
                "check": "pnpm -r --if-present check",
                "lint": "biome check .",
                "format": "biome format --write .",
                "test": "pnpm -r --if-present test",
                "build": "pnpm -r --if-present build",
                "graph:build": "uv run --no-project python tools/dev-spec/graph_gate.py build --root .",
                "graph:check": "uv run --no-project python tools/dev-spec/graph_gate.py check --root .",
                "graph:query": "uv run --no-project python tools/dev-spec/graph_gate.py query --root .",
            },
        }
        planned["package.json"] = (json.dumps(package, indent=2) + "\n").encode("utf-8")
        planned["pnpm-workspace.yaml"] = (
            "packages:\n"
            "  - 'apps/*'\n"
            "  - 'packages/*'\n"
            "\n"
            "# Centralized version catalog: pin resolved compatible versions here and reference via catalog:\n"
            "catalog: {}\n"
        ).encode("utf-8")
        planned["biome.json"] = (json.dumps(BIOME_CONFIG, indent=2) + "\n").encode("utf-8")

    if rust:
        channel = rust_version or "stable"
        planned["rust-toolchain.toml"] = (
            f'[toolchain]\nchannel = "{channel}"\ncomponents = ["rustfmt", "clippy"]\n'
        ).encode("utf-8")
        planned["deny.toml"] = CARGO_DENY_TEMPLATE.encode("utf-8")

    planned["docs/README.md"] = (
        "# 工程环境\n\n"
        "当前为 `BOOTSTRAP` 空骨架。按选型使用官方 CLI 生成真实应用，配置锁定版本、环境、契约、启动与测试并建立首份双图谱后，再将 `dev-spec.project.json` 的 `phase` 更新为 `READY`。\n\n"
        "- 使用 `dev.ps1` / `dev.cmd` / `dev.sh` 或 `pnpm dev` 启动开发预览；缺少应用或健康接口时会明确阻断并输出日志尾部摘要。\n"
        "- `.agents/hooks.json` 已配置生命周期门禁（`PreToolUse` 与 `Stop`），在 `READY` 阶段强制要求业务代码分析前完成 `graph_gate.py` 双图谱构建与查询。\n"
        "- 数据库若需自动启动，在明确初始化与 Expand-Contract 迁移策略后加入本地专用服务；严禁连接生产库作为预览。\n"
    ).encode("utf-8")

    root.mkdir(parents=True, exist_ok=True)
    for relative, content in planned.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        if relative == "dev.sh" and sys.platform != "win32":
            target.chmod(target.stat().st_mode | 0o111)
    local = root / ".dev-spec" / "local"
    local.mkdir(parents=True, exist_ok=True)
    (local / "python-executable.txt").write_text(sys.executable + "\n", encoding="utf-8")
    for component in components:
        (root / ("infra" if component == "database" else f"apps/{component}")).mkdir(
            parents=True, exist_ok=True
        )
    subprocess.run([git, "init", "--initial-branch=main", str(root)], check=True, capture_output=True)
    return {
        "root": str(root),
        "phase": "BOOTSTRAP",
        "created": sorted(planned),
        "installed_dependencies": [],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument(
        "--components",
        nargs="+",
        choices=["web", "api", "desktop", "database"],
        required=True,
    )
    parser.add_argument("--pnpm-version")
    parser.add_argument("--rust-version")
    args = parser.parse_args()
    try:
        print(
            json.dumps(
                initialize(
                    args.root,
                    args.name,
                    sorted(set(args.components)),
                    args.pnpm_version,
                    args.rust_version,
                ),
                ensure_ascii=False,
                indent=2,
            )
        )
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print(str(error), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
