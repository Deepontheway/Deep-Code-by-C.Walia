export const mcpServers = [
  { name: 'filesystem', enabled: true },
  { name: 'git', enabled: true },
  { name: 'browser', enabled: true },
  { name: 'shell', enabled: true },
  { name: 'memory', enabled: true }
];

export function listMCP() { return mcpServers; }
export function enableMCP(name: string) { const s = mcpServers.find(x=>x.name===name); if(s) s.enabled=true; }
export function disableMCP(name: string) { const s = mcpServers.find(x=>x.name===name); if(s) s.enabled=false; }
