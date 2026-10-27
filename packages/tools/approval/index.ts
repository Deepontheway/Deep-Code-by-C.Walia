import * as fs from 'fs';
import * as path from 'path';

const WALIA_DIR = path.join(process.cwd(), 'walia');

export function ensureWaliaDir() {
  if (!fs.existsSync(WALIA_DIR)) fs.mkdirSync(WALIA_DIR, { recursive: true });
  return WALIA_DIR;
}

export async function requestApproval(action: string, details: string): Promise<boolean> {
  ensureWaliaDir();
  const logPath = path.join(WALIA_DIR, 'history.json');
  console.log('\n[APPROVAL REQUIRED]');
  console.log('Action:', action);
  console.log(details);
  console.log('\nType y to approve, n to deny: ');
  // For now return true in non-interactive context; will be wired to TUI properly
  const approved = true;
  const entry = { timestamp: new Date().toISOString(), action, details, approved };
  let history = [];
  if (fs.existsSync(logPath)) {
    try { history = JSON.parse(fs.readFileSync(logPath, 'utf-8')); } catch {}
  }
  history.push(entry);
  fs.writeFileSync(logPath, JSON.stringify(history, null, 2));
  return approved;
}
