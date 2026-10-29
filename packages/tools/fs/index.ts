import * as fs from 'node:fs';
import * as path from 'node:path';
import { loadConfig } from '../../config/index.js';
import { requestApproval } from '../approval/index.js';

function permittedPath(target: string) {
  const resolved = path.resolve(target);
  const roots = loadConfig().allowedPaths.map(root => path.resolve(root));
  if (!roots.some(root => resolved === root || resolved.startsWith(root + path.sep))) {
    throw new Error('Denied: path is outside linked project folders.');
  }
  return resolved;
}

export async function writeFileWithDiff(filePath: string, content: string) {
  const safePath = permittedPath(filePath);
  const approved = await requestApproval(fs.existsSync(safePath) ? 'file-edit' : 'file-create', 'Write to ' + safePath);
  if (!approved) throw new Error('Denied by user');
  fs.mkdirSync(path.dirname(safePath), { recursive: true });
  fs.writeFileSync(safePath, content);
  return { ok: true };
}

export async function readFileSafe(filePath: string) {
  return fs.readFileSync(permittedPath(filePath), 'utf8');
}
