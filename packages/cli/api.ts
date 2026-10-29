export interface AppConfig {
  base_url: string;
  model: string;
  workspace: string;
  personality_mode: string;
  privacy_mode: string;
  api_key_configured: boolean;
}

export interface SessionInfo {
  id: string;
  title: string;
  created_at: number;
  updated_at: number;
}

export interface ChatMessage {
  role: string;
  content: string;
  created_at?: number;
}

export interface ApprovalInfo {
  id: string;
  kind: string;
  state: string;
  payload: Record<string, unknown>;
  summary?: string;
  created_at?: number;
}

export interface ChatResult {
  session_id: string;
  reply: string;
  pending_approvals: ApprovalInfo[];
  notice?: string | null;
}

export interface ProjectInfo {
  id: string;
  name: string;
  path: string;
  active?: boolean;
}

export interface UsageInfo {
  requests?: number;
  prompt_tokens?: number;
  completion_tokens?: number;
  total_tokens?: number;
  [key: string]: unknown;
}

export class ApiError extends Error {
  status: number;
  detail: string;
  data: Record<string, unknown>;

  constructor(status: number, detail: string, data: Record<string, unknown> = {}) {
    super(detail);
    this.status = status;
    this.detail = detail;
    this.data = data;
  }
}

export class ApiClient {
  readonly baseUrl: string;

  constructor(
    baseUrl = process.env.DEEPCODE_API ||
      `http://127.0.0.1:${process.env.WALIACODE_PORT || '8765'}`
  ) {
    this.baseUrl = baseUrl.replace(/\/+$/, '');
  }

  private async request<T>(path: string, init: RequestInit = {}, timeoutMs = 15000): Promise<T> {
    let response: Response;
    try {
      response = await fetch(this.baseUrl + path, {
        ...init,
        headers: { 'Content-Type': 'application/json', ...(init.headers || {}) },
        signal: AbortSignal.timeout(timeoutMs)
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      throw new ApiError(0, `Cannot reach the Deep Code backend at ${this.baseUrl}: ${message}`);
    }
    const text = await response.text();
    let body: unknown = null;
    try {
      body = text ? JSON.parse(text) : null;
    } catch {
      body = text;
    }
    if (!response.ok) {
      const data = body && typeof body === 'object' ? (body as Record<string, unknown>) : {};
      const detail = typeof data.detail === 'string' ? data.detail : response.statusText || 'Request failed';
      throw new ApiError(response.status, detail, data);
    }
    return body as T;
  }

  health() {
    return this.request<{ status: string; product?: string }>('/health', {}, 2500);
  }

  config() {
    return this.request<AppConfig>('/api/config');
  }

  saveConfig(patch: Partial<AppConfig> & { clear_api_key?: boolean; api_key?: string }) {
    return this.request<AppConfig>('/api/config', { method: 'PUT', body: JSON.stringify(patch) });
  }

  sessions() {
    return this.request<SessionInfo[]>('/api/sessions');
  }

  createSession() {
    return this.request<SessionInfo>('/api/sessions', { method: 'POST' });
  }

  messages(sessionId: string) {
    return this.request<ChatMessage[]>(`/api/sessions/${encodeURIComponent(sessionId)}/messages`);
  }

  chat(sessionId: string | null, message: string) {
    return this.request<ChatResult>(
      '/api/chat',
      { method: 'POST', body: JSON.stringify({ message, session_id: sessionId }) },
      180000
    );
  }

  approvals() {
    return this.request<ApprovalInfo[]>('/api/approvals');
  }

  decide(approvalId: string, approved: boolean) {
    return this.request<Record<string, unknown>>(`/api/approvals/${encodeURIComponent(approvalId)}/decision`, {
      method: 'POST',
      body: JSON.stringify({ approved })
    });
  }

  usage() {
    return this.request<UsageInfo>('/api/usage');
  }

  projects() {
    return this.request<{ projects: ProjectInfo[]; active: string }>('/api/projects');
  }

  addProject(path: string, name = '') {
    return this.request<{ project: ProjectInfo; active: string }>('/api/projects', {
      method: 'POST',
      body: JSON.stringify({ path, name, activate: true })
    });
  }

  activateProject(projectId: string) {
    return this.request<{ workspace: string; project: ProjectInfo }>(
      `/api/projects/${encodeURIComponent(projectId)}/activate`,
      { method: 'POST' }
    );
  }

  modelCatalog() {
    return this.request<{ models: Array<Record<string, unknown>> }>('/api/models/catalog');
  }

  activationStatus() {
    return this.request<{ activated: boolean; install_id: string }>('/api/activation/status');
  }

  activateCode(code: string) {
    return this.request<Record<string, unknown>>('/api/activation/activate', {
      method: 'POST',
      body: JSON.stringify({ code })
    });
  }
}

