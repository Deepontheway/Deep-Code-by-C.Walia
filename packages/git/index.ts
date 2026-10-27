import { simpleGit } from 'simple-git';

const git = simpleGit(process.cwd());

export async function gitStatus() { return git.status(); }
export async function gitAdd(files: string[] = ['.']) { return git.add(files); }
export async function gitCommit(message: string) { return git.commit(message); }
export async function gitLog(n = 5) { return git.log({ n }); }
export async function initRepo() { return git.init(); }
