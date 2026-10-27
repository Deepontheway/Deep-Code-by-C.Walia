import { execa } from 'execa';
import { requestApproval } from '../approval/index.js';

export async function runShell(cmd: string, shell: 'cmd' | 'powershell' = 'cmd') {
  const approved = await requestApproval('shell', JSON.stringify({ cmd, shell }, null, 2));
  if (!approved) throw new Error('Denied by user');
  if (shell === 'powershell') {
    return execa('powershell', ['-NoProfile', '-Command', cmd]);
  }
  return execa('cmd', ['/c', cmd]);
}
