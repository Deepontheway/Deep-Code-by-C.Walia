import * as fs from 'node:fs';
import * as path from 'node:path';
import * as os from 'node:os';

const CONFIG_DIR = process.env.DEEPCODE_HOME
  ? path.resolve(process.env.DEEPCODE_HOME)
  : path.join(os.homedir(), '.deepcode');
const CONFIG_FILE = path.join(CONFIG_DIR, 'config.json');

export interface DeepCodeConfig {
  defaultModel: string;
  ollamaBaseUrl: string;
  approvalMode: 'always' | 'smart';
  shell: 'cmd' | 'powershell' | 'bash';
  allowedPaths: string[];
  runtimeRoot: string;
  privacyMode: 'local-first' | 'cloud-with-consent';
  personalityMode: 'companion' | 'standard' | 'minimal';
  smtp?: { host: string; port: number; user: string; pass: string; from: string };
}

export function ensureConfig(): DeepCodeConfig {
  fs.mkdirSync(CONFIG_DIR, { recursive: true });
  if (!fs.existsSync(CONFIG_FILE)) {
    const config: DeepCodeConfig = {
      defaultModel: 'opencode/big-pickle',
      ollamaBaseUrl: 'http://localhost:11434/v1',
      approvalMode: 'always',
      shell: process.platform === 'win32' ? 'powershell' : 'bash',
      allowedPaths: [process.cwd()],
      runtimeRoot: CONFIG_DIR,
      privacyMode: 'local-first',
      personalityMode: 'companion'
    };
    fs.writeFileSync(CONFIG_FILE, JSON.stringify(config, null, 2));
    return config;
  }
  return JSON.parse(fs.readFileSync(CONFIG_FILE, 'utf8')) as DeepCodeConfig;
}

export function loadConfig(): DeepCodeConfig { return ensureConfig(); }
