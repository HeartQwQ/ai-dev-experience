"""Start only configured local development services and clean up owned processes."""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
from threading import Thread
import time
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import urlopen
import webbrowser

import graph_gate

MAX_PREV_LOG_BYTES = 5 * 1024 * 1024


def own_windows_job(process):
    """Keep a kernel handle to this process tree; do not enumerate unrelated PIDs."""
    if os.name != "nt":
        return
    import ctypes
    from ctypes import wintypes

    class BasicLimits(ctypes.Structure):
        _fields_ = [
            ("process_time", ctypes.c_longlong),
            ("job_time", ctypes.c_longlong),
            ("flags", wintypes.DWORD),
            ("minimum", ctypes.c_size_t),
            ("maximum", ctypes.c_size_t),
            ("active", wintypes.DWORD),
            ("affinity", ctypes.c_size_t),
            ("priority", wintypes.DWORD),
            ("scheduling", wintypes.DWORD),
        ]

    class IOCounters(ctypes.Structure):
        _fields_ = [
            (name, ctypes.c_ulonglong)
            for name in ("reads", "writes", "others", "read_bytes", "write_bytes", "other_bytes")
        ]

    class ExtendedLimits(ctypes.Structure):
        _fields_ = [
            ("basic", BasicLimits),
            ("io", IOCounters),
            ("process_memory", ctypes.c_size_t),
            ("job_memory", ctypes.c_size_t),
            ("peak_process", ctypes.c_size_t),
            ("peak_job", ctypes.c_size_t),
        ]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel.CreateJobObjectW.restype = wintypes.HANDLE
    kernel.SetInformationJobObject.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        ctypes.c_void_p,
        wintypes.DWORD,
    ]
    kernel.SetInformationJobObject.restype = wintypes.BOOL
    kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel.AssignProcessToJobObject.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL

    job = kernel.CreateJobObjectW(None, None)
    if not job:
        raise OSError(ctypes.get_last_error(), "Cannot create owned development job")
    limits = ExtendedLimits()
    limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    proc_handle = wintypes.HANDLE(int(process._handle))
    if not kernel.SetInformationJobObject(
        job, 9, ctypes.byref(limits), ctypes.sizeof(limits)
    ) or not kernel.AssignProcessToJobObject(job, proc_handle):
        error = ctypes.get_last_error()
        kernel.CloseHandle(job)
        raise OSError(error, "Cannot isolate the development process tree; startup refused")
    process._dev_spec_job = (kernel, job)


def local_url(url):
    value = urlparse(url)
    if value.scheme != "http" or value.hostname not in {"localhost", "127.0.0.1", "::1"} or value.username:
        raise ValueError("Development readiness/preview URLs must be local HTTP loopback URLs")
    return value


def configuration(root):
    config = json.loads((root / "dev-spec.project.json").read_text(encoding="utf-8"))
    if config.get("schema_version") != 1 or not config.get("services"):
        raise ValueError("Configure real development services in dev-spec.project.json first")
    names = set()
    for service in config["services"]:
        name = service.get("name", "")
        if not name or not all(c.isalnum() or c in "-_" for c in name) or name in names:
            raise ValueError("Development service names must be safe and unique")
        names.add(name)
        command = service.get("command")
        if not isinstance(command, list) or not command or not all(isinstance(x, str) and x for x in command):
            raise ValueError(f"{name}: command must be a nonempty argument array")
        for relative in service.get("required_paths", []):
            target = (root / relative).resolve()
            if not target.is_relative_to(root) or not target.is_file():
                raise ValueError(f"{name}: missing application file {relative}; generate the real application first")
        if service.get("ready_url"):
            local_url(service["ready_url"])
    if config.get("preview_url"):
        local_url(config["preview_url"])
    return config


def read_local_env(root):
    result = os.environ.copy()
    for name in (".env", ".env.development.local"):
        path = root / name
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            key, separator, value = line.partition("=")
            key = key.strip()
            if not separator or not key.replace("_", "a").isalnum() or key[0].isdigit():
                raise ValueError(
                    f"Unsupported environment assignment in {name}; use KEY=value without shell expansion"
                )
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            result[key] = value
    result["APP_ENV"] = "development"
    result.update(
        CODEGRAPH_TELEMETRY="0",
        DO_NOT_TRACK="1",
        GRAPHIFY_BACKEND="none",
        GRAPHIFY_QUERY_LOG_DISABLE="1",
    )
    return result


def _is_loopback_port_occupied(port):
    for host in ("127.0.0.1", "::1"):
        try:
            with socket.create_connection((host, port), timeout=0.25):
                return host
        except OSError:
            continue
    return None


def ensure_free_ports(config):
    for service in config["services"]:
        if not service.get("ready_url"):
            continue
        parsed = local_url(service["ready_url"])
        port = parsed.port or 80
        occupied_host = _is_loopback_port_occupied(port)
        if occupied_host:
            raise ValueError(
                f"{service['name']}: configured port {port} already occupied on {occupied_host}; "
                "inspect its owner instead of killing/replacing it"
            )


def tail_log(root, service_name, max_lines=30):
    log_path = root / ".dev-spec" / "local" / "logs" / f"{service_name}.log"
    if not log_path.is_file():
        return "(no log file generated)"
    try:
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        snippet = "\n".join(lines[-max_lines:]).strip()
        return snippet if snippet else "(log file is empty)"
    except OSError:
        return "(unable to read log file)"


def start_service(root, service, base_env):
    log_dir = root / ".dev-spec" / "local" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{service['name']}.log"
    if log_path.is_file() and log_path.stat().st_size > 0:
        prev_path = log_dir / f"{service['name']}.prev.log"
        data = log_path.read_bytes()[-MAX_PREV_LOG_BYTES:]
        prev_path.write_bytes(data)

    log = log_path.open("w", encoding="utf-8")
    command = list(service["command"])
    executable = shutil.which(command[0])
    if not executable:
        log.close()
        raise ValueError(f"{service['name']}: executable missing: {command[0]}")
    command[0] = executable
    env = dict(base_env)
    env.update(service.get("env", {}))
    env["APP_ENV"] = "development"
    options = (
        {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
        if os.name == "nt"
        else {"start_new_session": True}
    )
    try:
        process = subprocess.Popen(
            command,
            cwd=root,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            **options,
        )
        try:
            own_windows_job(process)
        except OSError:
            process.kill()
            process.wait(timeout=5)
            raise
    except OSError:
        log.close()
        raise
    return process, log


def wait_ready(root, process, service):
    deadline = time.monotonic() + service.get("timeout_seconds", 120)
    url = service.get("ready_url")
    name = service["name"]
    if not url:
        time.sleep(0.5)
        if process.poll() is not None:
            raise RuntimeError(
                f"{name} exited before readiness (code {process.returncode}).\n"
                f"--- Last log lines ({name}.log) ---\n{tail_log(root, name)}"
            )
        return
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(
                f"{name} exited before readiness (code {process.returncode}).\n"
                f"--- Last log lines ({name}.log) ---\n{tail_log(root, name)}"
            )
        try:
            with urlopen(url, timeout=0.5) as response:
                if 200 <= response.status < 400:
                    return
        except (OSError, URLError):
            pass
        time.sleep(0.2)
    raise RuntimeError(
        f"{name} readiness timed out after {service.get('timeout_seconds', 120)}s.\n"
        f"--- Last log lines ({name}.log) ---\n{tail_log(root, name)}"
    )


def stop_owned(process):
    job = getattr(process, "_dev_spec_job", None)
    if job:
        kernel, handle = job
        kernel.CloseHandle(handle)
        process._dev_spec_job = None
        process.wait(timeout=10)
        return
    if process.poll() is not None:
        return
    if os.name == "nt":
        result = subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            capture_output=True,
            timeout=15,
        )
        if result.returncode != 0 and process.poll() is None:
            process.terminate()
    else:
        os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        if os.name == "nt":
            process.kill()
        else:
            os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=5)


def start_graph_viewer(root):
    class LocalGraphHandler(SimpleHTTPRequestHandler):
        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        partial(LocalGraphHandler, directory=str(root / "graphify-out")),
    )
    server.daemon_threads = True
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, f"http://127.0.0.1:{server.server_port}/graph.html"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    owned = []
    graph_viewer = None
    pid_file = root / ".dev-spec" / "local" / "dev-supervisor.pid"
    try:
        config = configuration(root)
        env = read_local_env(root)
        ensure_free_ports(config)
        if args.check_only:
            print("Configuration preflight passed; graphs and application runtime have not been checked")
            return 0
        try:
            graph_gate.check(root)
        except graph_gate.GateError:
            print("Building/updating both local graphs and the offline visualization...", flush=True)
            graph_gate.build(root)
        graph_gate.query(root, config.get("graph_question", "application entry routes services"))
        pid_file.parent.mkdir(parents=True, exist_ok=True)
        pid_file.write_text(f"{os.getpid()}\n", encoding="utf-8")
        for service in config["services"]:
            process, log = start_service(root, service, env)
            owned.append((service["name"], process, log))
            wait_ready(root, process, service)
            print(f"Started {service['name']}; log: .dev-spec/local/logs/{service['name']}.log", flush=True)
        graph_viewer = start_graph_viewer(root)
        print(
            f"Development services started; local graph: {graph_viewer[2]}. Ctrl+C stops owned processes.",
            flush=True,
        )
        if not args.no_browser:
            if config.get("preview_url"):
                webbrowser.open(config["preview_url"])
            webbrowser.open(graph_viewer[2])
        while True:
            for name, process, _ in owned:
                if process.poll() is not None:
                    raise RuntimeError(
                        f"Development service '{name}' exited (code {process.returncode}).\n"
                        f"--- Last log lines ({name}.log) ---\n{tail_log(root, name)}"
                    )
            time.sleep(0.5)
    except KeyboardInterrupt:
        return 0
    except (OSError, ValueError, RuntimeError, graph_gate.GateError) as error:
        print(f"Development startup blocked: {error}", file=sys.stderr)
        return 2
    finally:
        pid_file.unlink(missing_ok=True)
        if graph_viewer:
            graph_viewer[0].shutdown()
            graph_viewer[0].server_close()
            graph_viewer[1].join(timeout=2)
        for _, process, log in reversed(owned):
            try:
                stop_owned(process)
            finally:
                log.close()


if __name__ == "__main__":
    sys.exit(main())
