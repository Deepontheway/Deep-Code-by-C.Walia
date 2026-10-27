import { runAgent } from '../core/agent/index.js';

export async function runCli() {
  console.log('Walia Code - Hybrid CLI Agent (opencode + aider)');
  console.log('Powered by qwen3-coder:14b and Big Pickle');
  console.log('');
  await runAgent();
}
