import * as fs from 'node:fs';
import * as path from 'node:path';
import { loadConfig } from '../config/index.js';

const RUNTIME_FOLDERS = ['bin', 'runtime', 'models', 'env', 'sandbox', 'plugins', 'data', 'training', 'cache', 'licenses'];

/** Creates only DeepCode-owned folders; it never installs software or downloads models without approval. */
export function ensureRuntimeLayout() {
  const root = loadConfig().runtimeRoot;
  for (const folder of RUNTIME_FOLDERS) fs.mkdirSync(path.join(root, folder), { recursive: true });
  return root;
}

export function runtimePath(...segments: string[]) {
  return path.join(ensureRuntimeLayout(), ...segments);
}
