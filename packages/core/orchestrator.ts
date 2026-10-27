import { runAgent } from './agent/index.js';
import { longTermMemory } from './memory/vector.js';
import { listMCP } from './mcp/index.js';

export async function orchestrate() {
  console.log('[Orchestrator] Initializing Deep Code by C.Walia...');
  console.log('[MCP]', listMCP().length, 'servers');
  console.log('[Memory]', longTermMemory().length, 'memories');
  await runAgent();
}
