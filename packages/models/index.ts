export type ModelLocation = 'local' | 'cloud';

export interface ModelProfile {
  id: string;
  name: string;
  provider: string;
  free: boolean;
  location: ModelLocation;
  downloadGB?: number;
  recommendedRamGB?: number;
  adapterCompatible?: boolean;
}

/** Product-facing names stay simple; required notices remain in releases. */
export const MODELS: ModelProfile[] = [
  { id: 'opencode/big-pickle', name: 'DeepCode Cloud', provider: 'opencode', free: true, location: 'cloud' },
  { id: 'qwen3-coder:14b', name: 'DeepCode Local', provider: 'ollama', free: true, location: 'local', downloadGB: 9, recommendedRamGB: 20, adapterCompatible: true },
  { id: 'qwen3-coder:30b', name: 'DeepCode Local Strong', provider: 'ollama', free: true, location: 'local', downloadGB: 18, recommendedRamGB: 32, adapterCompatible: true },
  { id: 'qwen2.5-coder:14b', name: 'DeepCode Local Balanced', provider: 'ollama', free: true, location: 'local', downloadGB: 9, recommendedRamGB: 20, adapterCompatible: true },
  { id: 'qwen2.5-coder:32b', name: 'DeepCode Local Max', provider: 'ollama', free: true, location: 'local', downloadGB: 20, recommendedRamGB: 40, adapterCompatible: true },
  { id: 'deepseek-coder-v2', name: 'DeepCode Local DeepSeek', provider: 'ollama', free: true, location: 'local', downloadGB: 10, recommendedRamGB: 24 },
  { id: 'openrouter/auto', name: 'Cloud provider (user key)', provider: 'openrouter', free: false, location: 'cloud' }
];

export const DEFAULT_MODEL = 'opencode/big-pickle';
export const OLLAMA_MODEL = 'qwen3-coder:14b';
export const OLLAMA_BASE_URL = 'http://localhost:11434/v1';

export function getDefaultModel() { return DEFAULT_MODEL; }
export function getFreeModels() { return MODELS.filter(model => model.free); }
export function getLocalModels() { return MODELS.filter(model => model.location === 'local'); }
