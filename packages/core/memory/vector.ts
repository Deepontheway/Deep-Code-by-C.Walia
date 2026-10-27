import * as fs from 'fs';
import * as path from 'path';

const MEMORY_DIR = path.join(process.cwd(), 'walia', 'memory');
if (!fs.existsSync(MEMORY_DIR)) fs.mkdirSync(MEMORY_DIR, { recursive: true });

export function storeMemory(key: string, value: any) {
  const p = path.join(MEMORY_DIR, key.replace(/[^a-z0-9]/gi,'_') + '.json');
  fs.writeFileSync(p, JSON.stringify({ key, value, ts: Date.now() }, null, 2));
}

export function recallMemory(key?: string) {
  if (!key) {
    const files = fs.readdirSync(MEMORY_DIR);
    return files.map(f => JSON.parse(fs.readFileSync(path.join(MEMORY_DIR,f),'utf-8')));
  }
  const p = path.join(MEMORY_DIR, key.replace(/[^a-z0-9]/gi,'_') + '.json');
  if (fs.existsSync(p)) return JSON.parse(fs.readFileSync(p,'utf-8'));
  return null;
}

export function longTermMemory() { return recallMemory(); }
