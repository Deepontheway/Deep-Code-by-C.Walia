import * as fs from 'fs';
import * as path from 'path';
import { ensureWaliaDir } from '../tools/approval/index.js';

export function initPlanning() {
  const dir = ensureWaliaDir();
  const files = {
    'task_plan.md': '# Walia Code Task Plan\n\n- [ ] Understand goal\n- [ ] Plan steps\n- [ ] Execute\n- [ ] Verify\n- [ ] Complete\n',
    'notes.md': '# Notes\n\n',
    'deliverable.md': '# Deliverable\n\n'
  };
  for (const [name, content] of Object.entries(files)) {
    const p = path.join(dir, name);
    if (!fs.existsSync(p)) fs.writeFileSync(p, content);
  }
  return dir;
}

export function readPlan() {
  const dir = ensureWaliaDir();
  const p = path.join(dir, 'task_plan.md');
  if (!fs.existsSync(p)) initPlanning();
  return fs.readFileSync(path.join(dir, 'task_plan.md'), 'utf-8');
}
