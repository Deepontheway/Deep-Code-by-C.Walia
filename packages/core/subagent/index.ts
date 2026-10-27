export interface SubAgentTask { goal: string; context?: string; maxTurns?: number; }

export async function spawnSubAgent(task: SubAgentTask) {
  console.log('[SUB-AGENT] Spawning for:', task.goal);
  // Placeholder - will integrate with model routing
  return { summary: 'Sub-agent completed task (scaffold)', filesChanged: [] };
}
