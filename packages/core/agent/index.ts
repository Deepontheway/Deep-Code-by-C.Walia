import { getDefaultModel } from '../models/index.js';
import { readPlan, initPlanning } from './planner/index.js';

export async function runAgent() {
  console.log('Walia Code Agent starting...');
  console.log('Default model:', getDefaultModel());
  initPlanning();
  console.log(readPlan());
}
