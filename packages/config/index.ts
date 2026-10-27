import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';

const CONFIG_DIR = path.join(os.homedir(), '.walia');
const CONFIG_FILE = path.join(CONFIG_DIR, 'config.json');

export interface WaliaConfig {
  defaultModel: string;
  useBigPickle: boolean;
  ollamaBaseUrl: string;
  approvalMode: 'always' | 'smart';
  shell: 'cmd' | 'powershell';
  smtp?: { host: string; port: number; user: string; pass: string; from: string };
  allowedPaths: string[];
}

export function ensureConfig(): WaliaConfig {
  if (!fs.existsSync(CONFIG_DIR)) fs.mkdirSync(CONFIG_DIR, { recursive: true });
  if (!fs.existsSync(CONFIG_FILE)) {
    const def: WaliaConfig = {
      defaultModel: 'opencode/big-pickle',
      useBigPickle: true,
      ollamaBaseUrl: 'http://localhost:11434/v1',
      approvalMode: 'always',
      shell: process.platform === 'win32' ? 'cmd' : 'bash',
      allowedPaths: [process.cwd()]
    };
    fs.writeFileSync(CONFIG_FILE, JSON.stringify(def, null, 2));
    return def;
  }
  return JSON.parse(fs.readFileSync(CONFIG_FILE, 'utf-8'));
}

export function loadConfig(): WaliaConfig { return ensureConfig(); }
