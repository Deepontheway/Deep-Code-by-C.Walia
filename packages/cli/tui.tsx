import { useEffect, useRef, useState } from 'react';
import { Box, Text, render, useApp, useInput } from 'ink';
import { ApiClient, ApiError, type AppConfig, type ApprovalInfo, type SessionInfo } from './api.js';

type Role = 'user' | 'assistant' | 'system' | 'error' | 'tool';

interface Line {
  id: number;
  role: Role;
  text: string;
}

const SPINNER = ['|', '/', '-', '\\'];
let nextLineId = 1;

function makeLine(role: Role, text: string): Line {
  return { id: nextLineId++, role, text };
}

const HELP = [
  'Commands:',
  '  /help                 Show this help',
  '  /new                  Start a new chat',
  '  /sessions             List recent chats',
  '  /open <number>        Open a chat from the list',
  '  /model [name]         Show or switch the model',
  '  /project [path]       List, link, or switch projects (/project clear to unset)',
  '  /models               Browse the model catalog',
  '  /usage                Show today\'s usage',
  '  /activate <code>      Activate this installation',
  '  /approve  /reject     Decide the pending approval',
  '  /clear                Clear the visible transcript',
  '  /quit                 Exit'
].join('\n');

function roleLabel(role: Role): string {
  if (role === 'user') return 'you';
  if (role === 'assistant') return 'deep code';
  if (role === 'tool') return 'tool';
  if (role === 'error') return 'error';
  return 'system';
}

function roleColor(role: Role): string {
  if (role === 'user') return 'cyan';
  if (role === 'assistant') return 'green';
  if (role === 'tool') return 'yellow';
  if (role === 'error') return 'red';
  return 'gray';
}

function projectName(workspace: string): string {
  if (!workspace) return 'no project';
  const parts = workspace.split(/[\\/]+/).filter(Boolean);
  return parts.length ? parts[parts.length - 1] : workspace;
}

function approvalSummary(approval: ApprovalInfo): string {
  if (approval.summary) return approval.summary;
  const payload = approval.payload || {};
  const value = payload.path || payload.command || payload.url || payload.model || payload.query;
  return typeof value === 'string' ? value.slice(0, 240) : JSON.stringify(payload).slice(0, 240);
}

function errorText(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 403) {
      return 'This installation is not activated. Use /activate <code> after the owner approves it.';
    }
    return error.detail;
  }
  return error instanceof Error ? error.message : String(error);
}

interface AppProps {
  client: ApiClient;
}

export function App({ client }: AppProps) {
  const { exit } = useApp();
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [sessions, setSessions] = useState<SessionInfo[]>([]);
  const [lines, setLines] = useState<Line[]>([
    makeLine('system', 'Deep Code terminal. Type a request, or /help for commands. Writes, commands, and web fetches need approval.')
  ]);
  const [input, setInput] = useState('');
  const [cursor, setCursor] = useState(0);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState('starting backend');
  const [pending, setPending] = useState<ApprovalInfo[]>([]);
  const [tick, setTick] = useState(0);
  const [activated, setActivated] = useState(true);
  const [installId, setInstallId] = useState('');
  const [history, setHistory] = useState<string[]>([]);
  const [historyIndex, setHistoryIndex] = useState(-1);
  const sessionRef = useRef<string | null>(null);
  const inputRef = useRef(input);
  const cursorRef = useRef(cursor);

  inputRef.current = input;
  cursorRef.current = cursor;

  const push = (role: Role, text: string) => {
    setLines((previous) => [...previous, makeLine(role, text)].slice(-60));
  };

  const refreshUsage = async () => {
    try {
      const usage = await client.usage();
      setStatus(
        `ready | ${usage.requests ?? 0} requests today | ${usage.total_tokens ?? 0} tokens`
      );
    } catch {
      setStatus('ready');
    }
  };

  const refreshConfig = async () => {
    try {
      const next = await client.config();
      setConfig(next);
      return next;
    } catch (error) {
      if (error instanceof ApiError && error.status === 403) {
        setActivated(false);
        try {
          const state = await client.activationStatus();
          setInstallId(state.install_id || '');
        } catch {
          /* keep the generic activation message */
        }
      }
      throw error;
    }
  };

  const openSession = async (session: SessionInfo) => {
    const messages = await client.messages(session.id);
    sessionRef.current = session.id;
    const restored = messages
      .filter((message) => message.role === 'user' || message.role === 'assistant')
      .map((message) => makeLine(message.role as Role, message.content));
    setLines([makeLine('system', `Chat: ${session.title}`), ...restored].slice(-60));
    setStatus('ready');
  };

  const createSession = async () => {
    const session = await client.createSession();
    sessionRef.current = session.id;
    setSessions((previous) => [session, ...previous]);
    setLines([makeLine('system', 'New chat started.')]);
    setStatus('ready');
    return session;
  };

  const refreshApprovals = async () => {
    try {
      const list = await client.approvals();
      setPending(list || []);
    } catch {
      /* polling failure is not fatal */
    }
  };

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const [nextConfig, nextSessions] = await Promise.all([refreshConfig(), client.sessions()]);
        if (!mounted) return;
        setConfig(nextConfig);
        setSessions(nextSessions);
        if (nextSessions.length) {
          await openSession(nextSessions[0]);
        } else {
          await createSession();
        }
        await refreshUsage();
      } catch (error) {
        if (mounted) push('error', errorText(error));
        if (mounted) setStatus('waiting for activation');
      }
    })();
    const timer = setInterval(() => {
      refreshApprovals();
    }, 3000);
    return () => {
      mounted = false;
      clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    if (!busy) return;
    const timer = setInterval(() => setTick((value) => value + 1), 110);
    return () => clearInterval(timer);
  }, [busy]);

  const saveConfig = async (patch: Partial<AppConfig>) => {
    const current = config || (await client.config());
    const saved = await client.saveConfig({
      base_url: current.base_url,
      model: current.model,
      workspace: current.workspace,
      personality_mode: current.personality_mode,
      privacy_mode: current.privacy_mode,
      ...patch
    });
    setConfig(saved);
    return saved;
  };

  const remember = (value: string) => {
    setHistory((previous) => [...previous.filter((item) => item !== value), value].slice(-50));
    setHistoryIndex(-1);
  };

  const decide = async (approved: boolean) => {
    const approval = pending[0];
    if (!approval || busy) return;
    setBusy(true);
    setStatus(approved ? 'applying approved action' : 'rejecting action');
    try {
      const result = await client.decide(approval.id, approved);
      push(
        'tool',
        `${approved ? 'Approved' : 'Rejected'} ${approval.kind}. ${JSON.stringify(result).slice(0, 600)}`
      );
      setPending((previous) => previous.filter((item) => item.id !== approval.id));
      await refreshUsage();
    } catch (error) {
      push('error', errorText(error));
      await refreshApprovals();
    } finally {
      setBusy(false);
    }
  };

  const runCommand = async (raw: string) => {
    const parts = raw.trim().split(/\s+/);
    const command = (parts.shift() || '').toLowerCase();
    const argument = parts.join(' ').trim();
    try {
      if (command === '/help') {
        push('system', HELP);
        return;
      }
      if (command === '/quit' || command === '/exit') {
        exit();
        return;
      }
      if (command === '/clear') {
        setLines([makeLine('system', 'Transcript cleared. History is still saved.')]);
        return;
      }
      if (command === '/new') {
        await createSession();
        return;
      }
      if (command === '/sessions') {
        if (!sessions.length) {
          push('system', 'No saved chats yet.');
          return;
        }
        push(
          'system',
          sessions
            .slice(0, 10)
            .map((session, index) => `${index + 1}. ${session.title}`)
            .join('\n')
        );
        return;
      }
      if (command === '/open') {
        const index = Number.parseInt(argument, 10) - 1;
        const session = sessions[index];
        if (!session) {
          push('error', 'Use /sessions to see valid chat numbers.');
          return;
        }
        await openSession(session);
        return;
      }
      if (command === '/model') {
        if (!argument) {
          const next = await refreshConfig();
          push('system', `Model: ${next.model}\nProvider: ${next.base_url}`);
          return;
        }
        const saved = await saveConfig({ model: argument });
        push('system', `Model switched to ${saved.model}.`);
        return;
      }
      if (command === '/project') {
        if (!argument || argument === 'list') {
          const data = await client.projects();
          if (!data.projects.length) {
            push('system', 'No linked projects. Use /project C:\\path\\to\\folder to link one.');
            return;
          }
          push(
            'system',
            data.projects
              .map((project) => `${project.active ? '*' : ' '} ${project.name}  ${project.path}`)
              .join('\n')
          );
          return;
        }
        if (argument === 'clear') {
          const saved = await saveConfig({ workspace: '' });
          push('system', `Active project cleared. Workspace: ${saved.workspace || '(none)'}`);
          return;
        }
        const result = await client.addProject(argument);
        setConfig((previous) => (previous ? { ...previous, workspace: result.active } : previous));
        push('system', `Active project: ${result.active}`);
        return;
      }
      if (command === '/usage') {
        const usage = await client.usage();
        push('system', JSON.stringify(usage, null, 2));
        return;
      }
      if (command === '/models') {
        const data = await client.modelCatalog();
        push(
          'system',
          data.models
            .slice(0, 18)
            .map((model) => {
              const label = String(model.label || model.id || 'model');
              const location = String(model.location || 'cloud');
              const installed = model.installed ? ' installed' : '';
              return `- ${label} [${location}]${installed}`;
            })
            .join('\n')
        );
        return;
      }
      if (command === '/activate') {
        if (!argument) {
          push('system', `Install ID: ${installId || 'unknown'}\nUse /activate <code> with the code from the owner.`);
          return;
        }
        await client.activateCode(argument);
        setActivated(true);
        await refreshConfig();
        const nextSessions = await client.sessions();
        setSessions(nextSessions);
        if (nextSessions.length) await openSession(nextSessions[0]);
        else await createSession();
        push('system', 'Activated. Welcome to Deep Code.');
        return;
      }
      if (command === '/approve' || command === '/reject') {
        await decide(command === '/approve');
        return;
      }
      push('error', `Unknown command ${command}. Use /help.`);
    } catch (error) {
      push('error', errorText(error));
    }
  };

  const sendMessage = async () => {
    if (busy) return;
    const text = inputRef.current.trim();
    if (!text) return;
    setInput('');
    setCursor(0);
    remember(text);
    push('user', text);
    if (text.startsWith('/')) {
      await runCommand(text);
      return;
    }
    if (!activated) {
      push('error', 'Activate first with /activate <code>.');
      return;
    }
    setBusy(true);
    setStatus('model is thinking');
    try {
      let sessionId = sessionRef.current;
      if (!sessionId) {
        const session = await createSession();
        sessionId = session.id;
      }
      const result = await client.chat(sessionId, text);
      sessionRef.current = result.session_id;
      push('assistant', result.reply);
      if (result.notice) push('system', result.notice);
      setPending(result.pending_approvals || []);
      await refreshUsage();
    } catch (error) {
      const message = errorText(error);
      if (error instanceof ApiError && error.status === 403) setActivated(false);
      push('error', message);
    } finally {
      setBusy(false);
    }
  };

  useInput((value, key) => {
    if (pending.length && !busy && inputRef.current === '') {
      if (value.toLowerCase() === 'y') {
        void decide(true);
        return;
      }
      if (value.toLowerCase() === 'n') {
        void decide(false);
        return;
      }
    }
    if (key.return) {
      void sendMessage();
      return;
    }
    if (key.ctrl && value === 'c') {
      exit();
      return;
    }
    if (key.upArrow) {
      if (!history.length) return;
      const next = historyIndex < 0 ? history.length - 1 : Math.max(0, historyIndex - 1);
      setHistoryIndex(next);
      setInput(history[next] || '');
      setCursor((history[next] || '').length);
      return;
    }
    if (key.downArrow) {
      if (historyIndex < 0) return;
      const next = historyIndex + 1;
      if (next >= history.length) {
        setHistoryIndex(-1);
        setInput('');
        setCursor(0);
      } else {
        setHistoryIndex(next);
        setInput(history[next] || '');
        setCursor((history[next] || '').length);
      }
      return;
    }
    if (key.leftArrow) {
      setCursor((current) => Math.max(0, current - 1));
      return;
    }
    if (key.rightArrow) {
      setCursor((current) => Math.min(inputRef.current.length, current + 1));
      return;
    }
    if (key.backspace || key.delete) {
      setInput((current) => {
        const at = cursorRef.current;
        if (at <= 0) return current;
        return current.slice(0, at - 1) + current.slice(at);
      });
      setCursor((current) => Math.max(0, current - 1));
      return;
    }
    if (key.ctrl || key.meta || key.tab || key.escape) return;
    if (value) {
      const at = cursorRef.current;
      setInput((current) => current.slice(0, at) + value + current.slice(at));
      setCursor(at + value.length);
      setHistoryIndex(-1);
    }
  });

  const visible = lines.slice(-18);
  const spinner = SPINNER[tick % SPINNER.length];
  const before = input.slice(0, cursor);
  const at = input[cursor] || ' ';
  const after = input.slice(cursor + 1);
  const approval = pending[0];

  return (
    <Box flexDirection="column">
      <Box borderStyle="round" borderColor="cyan" paddingX={1}>
        <Text bold color="cyan">
          Deep Code
        </Text>
        <Text dimColor> by C.Walia</Text>
        <Text color="gray">  |  </Text>
        <Text color="green">{config?.model || 'no model'}</Text>
        <Text color="gray">  |  </Text>
        <Text color="magenta">{projectName(config?.workspace || '')}</Text>
      </Box>

      <Box flexDirection="column" marginTop={1} paddingX={1}>
        {visible.map((line) => (
          <Box key={line.id} flexDirection="column" marginBottom={1}>
            <Text color={roleColor(line.role)}>{roleLabel(line.role)}</Text>
            <Text wrap="wrap">{line.text}</Text>
          </Box>
        ))}
      </Box>

      {approval ? (
        <Box borderStyle="round" borderColor="yellow" flexDirection="column" paddingX={1}>
          <Text color="yellow" bold>
            Approval needed: {approval.kind}
          </Text>
          <Text wrap="wrap">{approvalSummary(approval)}</Text>
          <Text dimColor>Press y to approve or n to reject.</Text>
        </Box>
      ) : null}

      <Box marginTop={1} borderStyle="single" borderColor="gray" paddingX={1}>
        <Text color="cyan">â¯ </Text>
        <Text wrap="wrap">
          {before}
          <Text inverse>{at}</Text>
          {after}
        </Text>
      </Box>
      <Box paddingX={1}>
        <Text color={busy ? 'yellow' : activated ? 'green' : 'red'}>
          {busy ? `${spinner} ${status}` : activated ? 'â— ready' : 'â— not activated'}
        </Text>
        <Text dimColor>
          {'  '}
          {pending.length ? `${pending.length} approval(s) pending` : status}
        </Text>
      </Box>
      <Box paddingX={1}>
        <Text dimColor>
          {activated
            ? '/help  /new  /model  /project  /usage  /quit'
            : `/activate <code>  install ID: ${installId || 'unknown'}  /help  /quit`}
        </Text>
      </Box>
    </Box>
  );
}

export function startTUI(client: ApiClient) {
  return render(<App client={client} />);
}

