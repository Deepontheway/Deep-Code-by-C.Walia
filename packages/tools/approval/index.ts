import * as fs from 'node:fs';
import * as path from 'node:path';
import * as readline from 'node:readline/promises';
import { stdin as input, stdout as output } from 'node:process';
import { loadConfig } from '../../config/index.js';

export function ensureWaliaDir() {
  const dataDir = path.join(loadConfig().runtimeRoot, 'data');
  fs.mkdirSync(dataDir, { recursive: true });
  return dataDir;
}

/** Never approve an action merely because a UI has not been wired yet. */
export async function requestApproval(action: string, details: string): Promise<boolean> {
  const dataDir = ensureWaliaDir();
  console.log('\n[APPROVAL REQUIRED]');
  console.log('Action:', action);
  console.log(details);
  let approved = false;
  if (input.isTTY && output.isTTY) {
    const prompt = readline.createInterface({ input, output });
    const answer = await prompt.question('Approve this action? [y/N] ');
    prompt.close();
    approved = /^y(?:es)?$/i.test(answer.trim());
  } else {
    console.log('Denied: non-interactive sessions cannot auto-approve actions.');
  }
  const logPath = path.join(dataDir, 'approval-history.json');
  let history: unknown[] = [];
  if (fs.existsSync(logPath)) {
    try { history = JSON.parse(fs.readFileSync(logPath, 'utf8')) as unknown[]; } catch { /* empty corrupt log */ }
  }
  history.push({ timestamp: new Date().toISOString(), action, details, approved });
  fs.writeFileSync(logPath, JSON.stringify(history, null, 2));
  return approved;
}
