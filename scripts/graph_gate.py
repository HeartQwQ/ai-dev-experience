"""Fail-closed dual graph workflow. Does not install tools or change host settings."""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from urllib.request import Request, urlopen

SOURCE_EXTENSIONS = {
    ".py", ".rs", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".svelte",
    ".vue", ".go", ".c", ".h", ".cpp", ".java", ".cs", ".sql", ".toml", ".json",
    ".yaml", ".yml", ".sh", ".ps1", ".cmd", ".css", ".html", ".proto", ".graphql", ".gql",
}
EXCLUDED_PARTS = {
    ".git", "node_modules", "target", "dist", "build", ".svelte-kit", ".venv",
    "__pycache__", ".pytest_cache", "coverage", "graphify-out", ".codegraph", ".dev-spec",
    ".next", ".turbo", ".output", ".vercel", "playwright-report", "test-results",
}
CONFIG_NAMES = {
    ".gitignore", ".graphifyignore", ".graphifyrc", "codegraph.json",
    "biome.json", "biome.jsonc", "mise.toml", "rust-toolchain.toml",
    "deny.toml", "pnpm-workspace.yaml",
}
MAX_SOURCE_FILE_BYTES = 32 * 1024 * 1024


class GateError(RuntimeError):
    pass


def local_env():
    env = os.environ.copy()
    env.update(
        GRAPHIFY_BACKEND="none",
        GRAPHIFY_NO_AUTO_REFRESH="1",
        GRAPHIFY_QUERY_LOG_DISABLE="1",
        GRAPHIFY_VIZ_NODE_LIMIT="5000",
        CODEGRAPH_TELEMETRY="0",
        DO_NOT_TRACK="1",
    )
    return env


def run(root, arguments, timeout=900):
    executable = shutil.which(arguments[0])
    if not executable:
        raise GateError(f"Missing required tool: {arguments[0]}; repair environment, no search fallback")
    try:
        completed = subprocess.run(
            [executable, *arguments[1:]],
            cwd=root,
            env=local_env(),
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise GateError(f"{arguments[0]}: {type(error).__name__}") from error
    if completed.returncode:
        raise GateError(
            f"{arguments[0]} exited {completed.returncode}:\n"
            f"{completed.stderr[-4000:]}\n{completed.stdout[-4000:]}"
        )
    return completed.stdout.rstrip("\r\n")


def fingerprint(root):
    top = Path(run(root, ["git", "rev-parse", "--show-toplevel"], 30)).resolve()
    if top != root:
        raise GateError("Use the exact Git monorepo root")
    files = run(
        root,
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        30,
    ).split("\0")
    digest = hashlib.sha256()
    count = 0
    total_bytes = 0
    for name in sorted(set(files)):
        if not name:
            continue
        relative = Path(name)
        if any(part in EXCLUDED_PARTS or part.startswith(".codegraph-") for part in relative.parts):
            continue
        if relative.name.startswith(".env") or (
            relative.suffix.lower() not in SOURCE_EXTENSIONS and relative.name not in CONFIG_NAMES
        ):
            continue
        path = root / relative
        if path.is_symlink():
            try:
                resolved = path.resolve()
            except OSError as error:
                raise GateError(f"Broken source symlink cannot be indexed: {name}") from error
            if not resolved.is_relative_to(root):
                raise GateError(f"Source symlink points outside repository root: {name}")
            if not resolved.is_file():
                continue
            target_path = resolved
        else:
            if not path.is_file():
                continue
            target_path = path

        size = target_path.stat().st_size
        if size > MAX_SOURCE_FILE_BYTES:
            raise GateError(
                f"Source file exceeds {MAX_SOURCE_FILE_BYTES // (1024 * 1024)} MiB indexing limit: {name}"
            )
        raw = target_path.read_bytes()
        digest.update(name.replace("\\", "/").encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(raw).digest())
        count += 1
        total_bytes += len(raw)
    if not count:
        raise GateError("No indexable files; generate the selected minimal project scaffold first (BOOTSTRAP)")
    return {"sha256": digest.hexdigest(), "files": count, "bytes": total_bytes}


def versions(root):
    return {name: run(root, [name, "--version"], 30) for name in ("graphify", "codegraph")}


def graph_files(root):
    graph = root / "graphify-out" / "graph.json"
    db_name = os.environ.get("CODEGRAPH_DIR", ".codegraph")
    db_relative = Path(db_name)
    if db_relative.is_absolute() or ".." in db_relative.parts:
        raise GateError("CODEGRAPH_DIR must be a project-relative index directory")
    db = root / db_relative / "codegraph.db"
    html = root / "graphify-out" / "graph.html"
    for path in (graph, db, html):
        if not path.is_file() or not path.stat().st_size:
            raise GateError(f"Required graph artifact missing/empty: {path.relative_to(root)}")
    data = json.loads(graph.read_text(encoding="utf-8"))
    if not data.get("nodes"):
        raise GateError("Graphify graph has no nodes; inspect grammar/exclusion and partial-result diagnostics")
    return graph, db, html


def _verify_sri(tag_text, content):
    integrity = re.search(r'\bintegrity=["\']([^"\']+)', tag_text, re.I)
    if not integrity:
        return
    valid = False
    for token in integrity.group(1).split():
        algorithm, _, expected = token.partition("-")
        if algorithm in {"sha256", "sha384", "sha512"}:
            actual = base64.b64encode(hashlib.new(algorithm, content).digest()).decode()
            valid |= actual == expected
    if not valid:
        raise GateError("Visualization asset integrity mismatch; do not keep a CDN fallback")


def _download_or_read_vendor_asset(url, target, tag_text):
    if target.exists():
        content = target.read_bytes()
    else:
        request = Request(url, headers={"User-Agent": "dev-spec-local-graph/0.2"})
        with urlopen(request, timeout=45) as response:
            content = response.read(8 * 1024 * 1024 + 1)
        if not content or len(content) > 8 * 1024 * 1024:
            raise GateError("Invalid visualization asset size")
    _verify_sri(tag_text, content)
    target.write_bytes(content)
    meta_path = target.with_suffix(target.suffix + ".source.json")
    meta_path.write_text(
        json.dumps(
            {
                "source": url,
                "sha256": hashlib.sha256(content).hexdigest(),
                "note": "Generated graph dependency; no project content sent",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def localize_html(html_path):
    """Localize Graphify's remote script/style assets (e.g. vis-network from any CDN), preserving SRI."""
    html = html_path.read_text(encoding="utf-8")
    vendor = html_path.parent / "vendor"
    script_pattern = re.compile(
        r'<script\b[^>]*\bsrc=["\'](https?://[^"\']*vis-network[^"\']*\.js)["\'][^>]*>\s*</script>|'
        r'<script\b[^>]*\bsrc=["\'](https?://[^"\']*vis-network[^"\']*\.js)["\'][^>]*>',
        re.I,
    )
    for match in list(script_pattern.finditer(html)):
        full_tag = match.group(0)
        url = match.group(1) or match.group(2)
        ver_match = re.search(r"vis-network[@/-]([0-9A-Za-z._-]+?)(?:/|\.min\.js|\.js)", url)
        version = ver_match.group(1) if ver_match else hashlib.sha256(url.encode("utf-8")).hexdigest()[:10]
        vendor.mkdir(exist_ok=True)
        target = vendor / f"vis-network-{version}.min.js"
        _download_or_read_vendor_asset(url, target, full_tag)
        # Also write legacy .source.json naming for backward compatibility
        legacy_meta = vendor / f"vis-network-{version}.source.json"
        legacy_meta.write_text(
            (target.with_suffix(target.suffix + ".source.json")).read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        local_tag = (
            f'<script src="vendor/{target.name}"></script>'
            if full_tag.lower().endswith("</script>")
            else f'<script src="vendor/{target.name}">'
        )
        html = html.replace(full_tag, local_tag)

    if re.search(r'<(?:script|link|iframe|img)\b[^>]*(?:src|href)=["\'](?:https?:)?//', html, re.I) or re.search(
        r'(?:@import|url\()\s*["\']?https?://', html, re.I
    ):
        raise GateError("Graph HTML still requires remote resources; localize/verify them before opening")
    html_path.write_text(html, encoding="utf-8", newline="\n")


def verify_html(html_path):
    html = html_path.read_text(encoding="utf-8")
    if re.search(r'<(?:script|link|iframe|img)\b[^>]*(?:src|href)=["\'](?:https?:)?//', html, re.I):
        raise GateError("Graph visualization still loads remote resources")
    for source in re.findall(r'<script\b[^>]*\bsrc=["\']([^"\']+)', html, re.I):
        target = (html_path.parent / source).resolve()
        if not target.is_relative_to(html_path.parent.resolve()) or not target.is_file():
            raise GateError("Graph visualization local resource missing or outside graph directory")
        if target.parent.name == "vendor":
            metadata = target.with_suffix(target.suffix + ".source.json")
            if not metadata.is_file():
                metadata = target.with_name(target.name.replace(".min.js", ".source.json"))
            try:
                expected = json.loads(metadata.read_text(encoding="utf-8"))["sha256"]
            except (OSError, KeyError, ValueError) as error:
                raise GateError("Visualization asset provenance missing") from error
            if expected != hashlib.sha256(target.read_bytes()).hexdigest():
                raise GateError("Local visualization asset changed; verify/rebuild before opening")


def state_path(root):
    return root / ".dev-spec" / "local" / "graph-state.json"


def build(root):
    before = fingerprint(root)
    tool_versions = versions(root)
    state_path(root).parent.mkdir(parents=True, exist_ok=True)
    state_path(root).unlink(missing_ok=True)
    state_path(root).with_name("last-query.json").unlink(missing_ok=True)
    run(root, ["graphify", "extract", ".", "--code-only"])
    run(root, ["graphify", "export", "html"])
    index = Path(os.environ.get("CODEGRAPH_DIR", ".codegraph"))
    if not index.is_absolute() and ".." not in index.parts and (root / index / "codegraph.db").exists():
        run(root, ["codegraph", "sync", "."])
    else:
        run(root, ["codegraph", "init", ".", "--yes"])
    graph, db, html = graph_files(root)
    localize_html(html)
    verify_html(html)
    if fingerprint(root) != before:
        raise GateError("Sources changed during indexing; refresh both graphs before analysis")
    data = {
        "root": str(root),
        "source": before,
        "tools": tool_versions,
        "graphify_sha256": hashlib.sha256(graph.read_bytes()).hexdigest(),
        "html_sha256": hashlib.sha256(html.read_bytes()).hexdigest(),
        "codegraph_index": str(db.relative_to(root)),
        "local_only": True,
        "built_at": datetime.now(timezone.utc).isoformat(),
    }
    state_path(root).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return data


def check(root):
    try:
        state = json.loads(state_path(root).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise GateError("No valid dual-graph state; run build first") from error
    graph, _, html = graph_files(root)
    verify_html(html)
    if (
        state.get("root") != str(root)
        or state.get("source") != fingerprint(root)
        or state.get("tools") != versions(root)
    ):
        raise GateError("Workspace/source/tool version changed; refresh both graphs")
    if (
        state.get("graphify_sha256") != hashlib.sha256(graph.read_bytes()).hexdigest()
        or state.get("html_sha256") != hashlib.sha256(html.read_bytes()).hexdigest()
    ):
        raise GateError("Graph artifacts changed; rebuild and verify the local visualization")
    run(root, ["codegraph", "status", "."], 60)
    return state


def query(root, question):
    if not question.strip():
        raise GateError("A real code-analysis question is required")
    state_path(root).with_name("last-query.json").unlink(missing_ok=True)
    check(root)
    results = {
        "graphify": run(root, ["graphify", "query", question], 120),
        "codegraph": run(root, ["codegraph", "explore", question], 120),
    }
    if not all(value.strip() for value in results.values()):
        raise GateError("A graph returned no output; refine the query or repair coverage")
    check(root)
    evidence = {
        "root": str(root),
        "question": question,
        "source": fingerprint(root),
        "at": datetime.now(timezone.utc).isoformat(),
        "results": results,
        "note": "Verify actual symbol/path hits and real source before claiming analysis complete",
    }
    path = state_path(root).with_name("last-query.json")
    path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["build", "check", "query"])
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--question", default="")
    args = parser.parse_args()
    root = args.root.resolve()
    try:
        if not root.is_dir():
            raise GateError("Project root does not exist")
        top = Path(run(root, ["git", "rev-parse", "--show-toplevel"], 30)).resolve()
        if top != root:
            raise GateError("Use the exact Git monorepo root; do not inherit another project's graph")
        result = {"build": build, "check": check}.get(args.action)
        data = result(root) if result else query(root, args.question)
        print(json.dumps({"status": "passed", "action": args.action, "evidence": data}, ensure_ascii=False, indent=2))
        return 0
    except (GateError, OSError, ValueError) as error:
        print(json.dumps({"status": "blocked", "reason": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
