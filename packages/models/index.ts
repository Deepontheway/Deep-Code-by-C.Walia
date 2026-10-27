export const MODELS = [
  { id: 'opencode/big-pickle', name: 'Big Pickle (Default)', provider: 'opencode', free: true },
  { id: 'qwen3-coder:480b', name: 'Qwen 3 Coder 480B (OpenCode)', provider: 'opencode', free: true },
  { id: 'qwen3-coder:235b-a22b', name: 'Qwen 3 Coder 235B MoE (OpenCode)', provider: 'opencode', free: true },
  { id: 'qwen3-coder:30b', name: 'Qwen 3 Coder 30B (Ollama)', provider: 'ollama', free: true, local: true },
  { id: 'qwen3-coder:14b', name: 'Qwen 3 Coder 14B (Ollama)', provider: 'ollama', free: true, local: true },
  { id: 'qwen2.5-coder:32b', name: 'Qwen 2.5 Coder 32B (Ollama)', provider: 'ollama', free: true, local: true },
  { id: 'qwen2.5-coder:14b', name: 'Qwen 2.5 Coder 14B (Ollama)', provider: 'ollama', free: true, local: true },
  { id: 'deepseek-v3.1', name: 'DeepSeek V3.1 (OpenCode)', provider: 'opencode', free: true },
  { id: 'deepseek-chat-v3-0324', name: 'DeepSeek V3 0324 (OpenCode)', provider: 'opencode', free: true },
  { id: 'deepseek-coder-v2:236b', name: 'DeepSeek Coder V2 236B (Ollama)', provider: 'ollama', free: true, local: true },
  { id: 'deepseek-coder-v2', name: 'DeepSeek Coder V2 (Ollama)', provider: 'ollama', free: true, local: true },
  { id: 'deepseek-r1-distill-qwen-32b', name: 'DeepSeek R1 Distill Qwen 32B (Ollama)', provider: 'ollama', free: true, local: true },
  { id: 'deepseek-r1-distill-qwen-14b', name: 'DeepSeek R1 Distill Qwen 14B (Ollama)', provider: 'ollama', free: true, local: true },
  { id: 'kimi-k2', name: 'Kimi K2 (OpenCode)', provider: 'opencode', free: true },
  { id: 'kimi-k2.1', name: 'Kimi K2.1 (OpenCode)', provider: 'opencode', free: true },
  { id: 'grok-code-fast-1', name: 'Grok Code Fast 1 (OpenCode)', provider: 'opencode', free: true },
  { id: 'seed-coder:36b', name: 'Seed Coder 36B (Ollama)', provider: 'ollama', free: true, local: true },
  { id: 'seed-coder', name: 'Seed Coder (Ollama)', provider: 'ollama', free: true, local: true },
  { id: 'codestral', name: 'Codestral (OpenCode)', provider: 'opencode', free: true },
  { id: 'claude-sonnet-4.5', name: 'Claude Sonnet 4.5 (OpenCode)', provider: 'opencode', free: true },
  { id: 'sonnet-4.5', name: 'Sonnet 4.5 (OpenCode)', provider: 'opencode', free: true },
  { id: 'cerebras-llama-3.1-8b', name: 'Cerebras Fast Models (OpenCode)', provider: 'opencode', free: true }
];

export const DEFAULT_MODEL = 'opencode/big-pickle';
export const OLLAMA_MODEL = 'qwen3-coder:14b';
export const OLLAMA_BASE_URL = 'http://localhost:11434/v1';

export function getDefaultModel() { return DEFAULT_MODEL; }
export function getFreeModels() { return MODELS.filter(m => m.free); }
