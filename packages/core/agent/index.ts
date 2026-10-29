import { getDefaultModel } from '../../models/index.js';
import { readPlan, initPlanning } from '../planner/index.js';

export async function runAgent() {
  console.log('DeepCode agent starting...');
  console.log('Default model:', getDefaultModel());
  initPlanning();
  console.log(readPlan());
}
