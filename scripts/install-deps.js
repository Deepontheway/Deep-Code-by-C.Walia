#!/usr/bin/env node
import { execSync } from 'child_process';
import { existsSync } from 'fs';
import { platform } from 'os';

function run(cmd) {
  console.log('> ' + cmd);
  try { execSync(cmd, { stdio: 'inherit' }); } catch(e) { console.log('warn:', e.message); }
}

console.log('Deep Code by C.Walia - Dependency Installer');
console.log('Platform:', platform());

if (platform() === 'win32') {
  console.log('Checking winget/choco...');
  if (existsSync('C:/Program Files/nodejs/node.exe')) console.log('Node.js found');
  else console.log('Node.js not found - will be handled by environment');
  
  // Try to install common tools if available
  try { run('winget install --id Microsoft.SQLServer.2022.Express -e --accept-package-agreements --accept-source-agreements'); } catch {}
  try { run('winget install --id PostgreSQL.PostgreSQL -e --accept-package-agreements --accept-source-agreements'); } catch {}
  try { run('winget install --id Ollama.Ollama -e --accept-package-agreements --accept-source-agreements'); } catch {}
  try { run('winget install --id Git.Git -e --accept-package-agreements --accept-source-agreements'); } catch {}
}

console.log('Done');
