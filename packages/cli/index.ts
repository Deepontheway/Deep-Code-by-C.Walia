import { runAgent } from '../core/agent/index.js';
import { startTUI } from './tui.js';

export async function runCli() {
  console.log('Deep Code by C.Walia - Hybrid CLI Agent');
  console.log('Powered by opencode/big-pickle + free models + local Ollama');
  console.log('');
  startTUI();
  await runAgent();
}
