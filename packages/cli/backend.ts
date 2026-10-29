import { spawn, type ChildProcess } from 'node:child_process';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';
import { ApiClient } from './api.js';

export interface BackendHandle {
  client: ApiClient;
  started: boolean;
  stop(): void;
}

function findAppRoot(): string | null {
  const starts = [process.cwd(), path.dirname(fileURLToPath(import.meta.url))];
  for (const start of starts) {
    let current = path.resolve(start);
    for (let depth = 0; depth < 7; depth += 1) {
      if (fs.existsSync(path.join(current, 'app', 'walia', 'run.py'))) return current;
      const parent = path.dirname(current);
      if (parent === current) break;
      current = parent;
    }
  }
  return null;
}

function findPython(root: string): string {
  const explicit = process.env.DEEPCODE_PYTHON || process.env.WALIACODE_PYTHON;
  if (explicit && fs.existsSync(explicit)) return explicit;
  const candidates = [
    path.join(root, 'venv', 'Scripts', 'python.exe'),
    path.join(root, '.venv', 'Scripts', 'python.exe'),
    path.join(root, 'venv', 'bin', 'python'),
    path.join(root, '.venv', 'bin', 'python')
  ];
  return candidates.find((candidate) => fs.existsSync(candidate)) || 'python';
}

async function waitForHealth(client: ApiClient, timeoutMs: number): Promise<boolean> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const health = await client.health();
      if (health.status === 'ok' && (!health.product || health.product === 'DeepCode')) return true;
    } catch {
      await new Promise((resolve) => setTimeout(resolve, 600));
    }
  }
  return false;
}

export async function ensureBackend(): Promise<BackendHandle> {
  const client = new ApiClient();
  if (await waitForHealth(client, 1200)) {
    return { client, started: false, stop() {} };
  }

  const root = findAppRoot();
  if (!root) {
    throw new Error(
      'Could not find app/walia/run.py. Run the terminal UI from the Deep Code folder, or start the web app first.'
    );
  }

  const python = findPython(root);
  let child: ChildProcess | null = spawn(python, ['-m', 'app.walia.run'], {
    cwd: root,
    windowsHide: true,
    stdio: 'ignore',
    env: {
      ...process.env,
      DEEPCODE_NO_BROWSER: '1',
      PYTHONUNBUFFERED: '1'
    }
  });
  child.on('error', () => {
    child = null;
  });

  const ready = await waitForHealth(client, 60000);
  if (!ready) {
    child?.kill();
    throw new Error(
      `The Deep Code backend did not start with "${python}". Start it manually with: ${python} -m app.walia.run`
    );
  }

  let stopped = false;
  const stop = () => {
    if (stopped) return;
    stopped = true;
    if (child && child.exitCode === null) {
      child.kill();
    }
  };
  process.once('exit', stop);
  process.once('SIGINT', () => {
    stop();
    process.exit(0);
  });

  return { client, started: true, stop };
}

