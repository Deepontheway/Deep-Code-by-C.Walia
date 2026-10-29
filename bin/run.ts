import { runCli } from '../packages/cli/index.js';

runCli().catch((error: unknown) => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exit(1);
});
