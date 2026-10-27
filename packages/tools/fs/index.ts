import * as fs from 'fs';
import { requestApproval } from '../approval/index.js';

export async function writeFileWithDiff(path: string, content: string) {
  const exists = fs.existsSync(path);
  await requestApproval(exists?'file-edit':'file-create', Write to );
  console.log('[DIFF PREVIEW] Ready');
  fs.writeFileSync(path, content);
  return { ok: true };
}

export async function readFileSafe(path: string) {
  return fs.readFileSync(path,'utf-8');
}
