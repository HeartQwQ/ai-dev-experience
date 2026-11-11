"""Read-only environment inventory; Python 3.10+, standard library only."""
import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys


def clean_env():
    env = os.environ.copy()
    env.update(
        GRAPHIFY_BACKEND="none",
        GRAPHIFY_NO_AUTO_REFRESH="1",
        GRAPHIFY_QUERY_LOG_DISABLE="1",
        CODEGRAPH_TELEMETRY="0",
        DO_NOT_TRACK="1",
    )
    return env


def inspect_tool(name, required):
    executable = shutil.which(name)
    if not executable:
        return {"tool": name, "required": required, "status": "missing"}
    try:
        result = subprocess.run(
            [executable, "--version"],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=20,
            env=clean_env(),
        )
        summary = (result.stdout or result.stderr).strip().splitlines()
        return {
            "tool": name,
            "required": required,
            "status": "ok" if result.returncode == 0 else "failed",
            "executable": executable,
            "version_output": summary[:3],
            "exit_code": result.returncode,
        }
    except (OSError, subprocess.TimeoutExpired) as error:
        return {
            "tool": name,
            "required": required,
            "status": "failed",
            "reason": type(error).__name__,
        }


def inspect_rust_components():
    rustup = shutil.which("rustup")
    if not rustup:
        return {"rustfmt": "unknown", "clippy": "unknown"}
    try:
        result = subprocess.run(
            [rustup, "component", "list", "--installed"],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=15,
            env=clean_env(),
        )
        installed = result.stdout.splitlines() if result.returncode == 0 else []
        return {
            "rustfmt": "installed" if any(x.startswith("rustfmt") for x in installed) else "missing",
            "clippy": "installed" if any(x.startswith("clippy") for x in installed) else "missing",
        }
    except (OSError, subprocess.TimeoutExpired):
        return {"rustfmt": "unknown", "clippy": "unknown"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument(
        "--features",
        nargs="*",
        choices=["web", "api", "desktop", "database"],
        default=[],
    )
    parser.add_argument(
        "--database-mode",
        choices=["local", "container", "remote"],
        default="local",
    )
    args = parser.parse_args()
    root = args.root.resolve()
    if not root.is_dir():
        parser.error("--root must be an existing project directory")
    required = {"git", "graphify", "codegraph"}
    optional = {"uv", "mise"}
    feature_set = set(args.features)
    if {"web", "desktop"} & feature_set:
        required.update(["node", "pnpm"])
        optional.add("biome")
    if {"api", "desktop"} & feature_set:
        required.update(["rustup", "rustc", "cargo"])
        optional.update(["cargo-nextest", "cargo-deny"])
    if "database" in feature_set:
        required.add("docker" if args.database_mode == "container" else "psql")
        optional.add("sqlx")
    tools = [inspect_tool(name, name in required) for name in sorted(required | optional)]
    result = {
        "root": str(root),
        "os": platform.system(),
        "architecture": platform.machine(),
        "python": {
            "executable": sys.executable,
            "version": platform.python_version(),
        },
        "features": args.features,
        "tools": tools,
        "rust_components": inspect_rust_components() if ({"api", "desktop"} & feature_set) else None,
        "unverified": [
            "latest stable compatibility",
            "native desktop prerequisites",
            "ports/process ownership",
            "database connectivity",
            "graph indexes and queries",
            "application build/runtime",
        ],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 2 if any(x["required"] and x["status"] != "ok" for x in tools) else 0


if __name__ == "__main__":
    sys.exit(main())
