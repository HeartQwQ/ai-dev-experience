import { existsSync, readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { execFileSync, spawn } from 'node:child_process';

const root = dirname(fileURLToPath(import.meta.url));
const record = join(root, '.dev-spec', 'local', 'python-executable.txt');
const recorded = existsSync(record) ? readFileSync(record, 'utf8').trim() : '';

function resolvePython() {
  if (process.env.DEV_SPEC_PYTHON) return process.env.DEV_SPEC_PYTHON;
  if (recorded && existsSync(recorded)) return recorded;
  try {
    const uvPy = execFileSync('uv', ['python', 'find'], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }).trim();
    if (uvPy && existsSync(uvPy)) return uvPy;
  } catch {}
  return process.platform === 'win32' ? 'python' : 'python3';
}

const python = resolvePython();
const child = spawn(python, [join(root, 'tools', 'dev-spec', 'dev.py'), '--root', root, ...process.argv.slice(2)], { cwd: root, stdio: 'inherit' });
child.on('error', error => { console.error(`Python launcher failed: ${error.message}`); process.exitCode = 2; });
child.on('exit', (code, signal) => { process.exitCode = code ?? (signal ? 1 : 0); });
