import { requestApproval } from '../approval/index.js';

export async function browse(url: string, action: string) {
  const approved = await requestApproval('browser', 'Navigate to ' + url + ' and ' + action);
  if (!approved) throw new Error('Denied by user');
  return { ok: true, url, action };
}

export async function scrape(url: string) {
  const approved = await requestApproval('browser-scrape', 'Scrape ' + url);
  if (!approved) throw new Error('Denied by user');
  return { ok: true, data: [] };
}

export async function automate() { return browse('about:blank', 'open an isolated browser session'); }
