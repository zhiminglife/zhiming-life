import type {
  BirthInfo,
  Chart,
  Evidence,
  LibraryKind,
  LibrarySource,
  LibraryStatus,
  Message,
  ModelSettings,
  Person,
  Session,
} from "./types";

type ApiRuntime = { base_url: string; token: string };

let runtimePromise: Promise<ApiRuntime> | null = null;

export async function waitForLocalApi(
  baseUrl: string,
  attempts = 120,
  delayMs = 500,
): Promise<void> {
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    try {
      const response = await fetch(`${baseUrl}/api/health`);
      if (response.ok) return;
    } catch {
      // The bundled sidecar is still extracting or initializing its local models.
    }
    if (attempt < attempts - 1) {
      await new Promise((resolve) => window.setTimeout(resolve, delayMs));
    }
  }
  throw new Error("本地服务启动超时，请重新连接");
}

function runtime(): Promise<ApiRuntime> {
  if (!runtimePromise) {
    runtimePromise = "__TAURI_INTERNALS__" in window
      ? import("@tauri-apps/api/core").then(async ({ invoke }) => {
          const api = await invoke<ApiRuntime>("api_runtime");
          await waitForLocalApi(api.base_url);
          return api;
        })
      : Promise.resolve({
          base_url: "",
          token: (import.meta.env.VITE_ZHIMING_API_TOKEN as string | undefined) ?? "",
        });
  }
  return runtimePromise;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const api = await runtime();
  let response: Response | null = null;
  for (let attempt = 0; attempt < 20; attempt += 1) {
    try {
      response = await fetch(`${api.base_url}${path}`, {
        ...init,
        headers: {
          "Content-Type": "application/json",
          ...(api.token ? { "X-Zhiming-Token": api.token } : {}),
          ...init?.headers,
        },
      });
      break;
    } catch (error) {
      if (attempt === 19) throw error;
      await new Promise((resolve) => window.setTimeout(resolve, 250));
    }
  }
  if (!response) throw new Error("本地服务未启动");
  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: "本地服务暂时不可用" }));
    throw new Error(error.message || "请求失败");
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export const getModelSettings = () => request<ModelSettings>("/api/settings/model");

export const saveModelSettings = (payload: {
  base_url: string;
  model: string;
  api_key?: string;
}) => request<ModelSettings>("/api/settings/model", { method: "PUT", body: JSON.stringify(payload) });

export const testModelSettings = () =>
  request<{ status: string }>("/api/settings/model/test", { method: "POST" });

export const listPersons = () => request<Person[]>("/api/persons");

export const createPerson = (payload: {
  name: string;
  relationship: string;
  birth: BirthInfo;
  notes: string;
}) => request<Person>("/api/persons", { method: "POST", body: JSON.stringify(payload) });

export const listSessions = (personId: string) =>
  request<Session[]>(`/api/sessions?person_id=${encodeURIComponent(personId)}`);

export const createSession = (payload: {
  primary_person_id: string;
  secondary_person_id?: string | null;
  title: string;
}) => request<Session>("/api/sessions", { method: "POST", body: JSON.stringify(payload) });

export const listMessages = (sessionId: string) =>
  request<Message[]>(`/api/sessions/${sessionId}/messages`);

export const sendMessage = (sessionId: string, content: string) =>
  request<{ user_message: Message; assistant_message: Message; evidence: Evidence[] }>(
    `/api/sessions/${sessionId}/messages`,
    { method: "POST", body: JSON.stringify({ content }) },
  );

export const getChart = (personId: string) =>
  request<Chart>(`/api/persons/${personId}/chart`);

export const getLibraryStatuses = () => request<LibraryStatus[]>("/api/libraries");

export const listLibrarySources = (kind: LibraryKind) =>
  request<LibrarySource[]>(`/api/libraries/${kind}/sources`);

export const deleteLibrarySource = (kind: LibraryKind, sourceId: string) =>
  request<void>(`/api/libraries/${kind}/sources/${sourceId}`, { method: "DELETE" });

export const importLibrary = (kind: LibraryKind, payload: {
  title: string;
  source_name: string;
  content: string;
  confirmed_anonymized: boolean;
}) => request<{ source_id: string; status: string; chunk_count: number }>(
  `/api/libraries/${kind}/import`,
  { method: "POST", body: JSON.stringify(payload) },
);
