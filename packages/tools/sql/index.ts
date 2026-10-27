import { execa } from 'execa';
import { requestApproval } from '../approval/index.js';

export async function runSql(query: string, client: 'sqlcmd' | 'psql' | 'sqlite3' | 'mysql' = 'sqlcmd') {
  const lowered = query.toLowerCase();
  if (lowered.includes('drop') || lowered.includes('truncate') || lowered.includes('alter')) {
    console.log('[WARNING] Potentially destructive SQL detected');
  }
  const approved = await requestApproval('sql', JSON.stringify({ client, query }, null, 2));
  if (!approved) throw new Error('Denied by user');
  // Placeholder - will wire actual client args
  return execa(client, ['-Q', query]);
}
