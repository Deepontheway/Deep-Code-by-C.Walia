export const DEFAULT_MODEL = 'opencode/big-pickle';
export const OLLAMA_MODEL = 'qwen3-coder:14b';
export const OLLAMA_BASE_URL = 'http://localhost:11434/v1';

export const MODELS = [
  { id: 'opencode/big-pickle', name: 'Big Pickle (Default)', provider: 'opencode' },
  { id: 'qwen3-coder:14b', name: 'qwen3-coder:14b (Ollama)', provider: 'ollama' },
  { id: 'grok-code-fast-1', name: 'grok-code-fast-1', provider: 'opencode' }
];

export function getDefaultModel() { return DEFAULT_MODEL; }
