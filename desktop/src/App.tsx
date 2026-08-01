import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  BookOpen,
  ChevronRight,
  CirclePlus,
  Database,
  ExternalLink,
  FileUp,
  Library,
  LoaderCircle,
  MessageSquareText,
  PanelRightClose,
  Send,
  Settings,
  Trash2,
  UserRoundPlus,
  UsersRound,
  X,
} from "lucide-react";

import * as api from "./api";
import { MODEL_PROVIDER_DEFAULTS } from "./model-providers";
import type { Chart, Evidence, LibraryKind, LibrarySource, LibraryStatus, Message, ModelProtocol, ModelSettings, Person, Session } from "./types";

const relationshipLabels: Record<string, string> = {
  self: "自己",
  family: "家人",
  partner: "伴侣",
  friend: "朋友",
  client: "来访者",
  other: "其他",
};

const ZHIMING_LIFE_URL = "https://zhiming.life/";

async function openZhimingLife(event: React.MouseEvent<HTMLAnchorElement>) {
  event.preventDefault();
  if ("__TAURI_INTERNALS__" in window) {
    const { openUrl } = await import("@tauri-apps/plugin-opener");
    await openUrl(ZHIMING_LIFE_URL);
    return;
  }
  window.open(ZHIMING_LIFE_URL, "_blank", "noopener,noreferrer");
}

function ZhimingLifeLink({ compact = false }: { compact?: boolean }) {
  return (
    <a className={compact ? "site-link compact" : "site-link"} href={ZHIMING_LIFE_URL} onClick={(event) => void openZhimingLife(event)}>
      <ExternalLink size={compact ? 11 : 13} />访问 zhiming.life 在线版
    </a>
  );
}

function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <section className="modal-card" role="dialog" aria-modal="true" aria-label={title}>
        <header><div><span className="eyebrow">知命 · 本地</span><h2>{title}</h2></div><button className="icon-button" onClick={onClose} aria-label="关闭"><X size={18} /></button></header>
        {children}
      </section>
    </div>
  );
}

function ChoiceField({
  legend,
  name,
  defaultValue,
  options,
  className = "",
}: {
  legend: string;
  name: string;
  defaultValue: string;
  options: { value: string; label: string }[];
  className?: string;
}) {
  return (
    <fieldset className={`choice-field ${className}`}>
      <legend>{legend}</legend>
      <div>
        {options.map((option) => (
          <label key={option.value}>
            <input type="radio" name={name} value={option.value} aria-label={option.label} defaultChecked={option.value === defaultValue} />
            <span>{option.label}</span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}

function ModelSettingsFields({
  initial,
  submitLabel,
  onSaved,
  onCancel,
}: {
  initial: ModelSettings;
  submitLabel: string;
  onSaved: (settings: ModelSettings) => void;
  onCancel?: () => void;
}) {
  const [protocol, setProtocol] = useState<ModelProtocol>(initial.protocol);
  const [baseUrl, setBaseUrl] = useState(initial.base_url);
  const [model, setModel] = useState(initial.model);
  const [apiKey, setApiKey] = useState("");
  const [busy, setBusy] = useState<"saving" | "testing" | null>(null);
  const [error, setError] = useState("");

  function chooseProtocol(nextProtocol: ModelProtocol) {
    const defaults = MODEL_PROVIDER_DEFAULTS[nextProtocol];
    setProtocol(nextProtocol);
    setBaseUrl(defaults.base_url);
    setModel(defaults.model);
    setApiKey("");
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy("saving"); setError("");
    try {
      const saved = await api.saveModelSettings({ protocol, base_url: baseUrl, model, api_key: apiKey || undefined });
      setBusy("testing");
      await api.testModelSettings();
      onSaved(saved);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "保存失败");
    } finally { setBusy(null); }
  }

  const keyRequired = !initial.has_api_key || protocol !== initial.protocol;

  return (
    <form onSubmit={submit} className="form-stack model-settings-form">
      <fieldset className="provider-picker">
        <legend>API 模式</legend>
        {Object.entries(MODEL_PROVIDER_DEFAULTS).map(([value, provider]) => (
          <label key={value} className={protocol === value ? "active" : ""}>
            <input
              type="radio"
              name="protocol"
              value={value}
              aria-label={provider.label}
              checked={protocol === value}
              onChange={() => chooseProtocol(value as ModelProtocol)}
            />
            <span><strong>{provider.label}</strong><small>{provider.hint}</small></span>
          </label>
        ))}
      </fieldset>
      <label>接口地址<input value={baseUrl} onChange={(event) => setBaseUrl(event.target.value)} required /></label>
      <label>模型名称<input value={model} onChange={(event) => setModel(event.target.value)} required /></label>
      <label>API Key<input aria-label="API Key" type="password" value={apiKey} onChange={(event) => setApiKey(event.target.value)} placeholder={keyRequired ? "只写入系统密钥库" : "已安全保存；留空不修改"} required={keyRequired} /></label>
      {error && <p className="form-error">{error}</p>}
      <div className="form-actions">
        {onCancel && <button type="button" className="quiet-button" onClick={onCancel}>取消</button>}
        <button className="primary-button" disabled={busy !== null}>
          {busy === "saving" ? <><LoaderCircle className="spin" size={15} />正在保存设置…</> : busy === "testing" ? <><LoaderCircle className="spin" size={15} />正在测试模型连接…</> : submitLabel}
        </button>
      </div>
    </form>
  );
}

function ModelSetup({ initial, onSaved }: { initial: ModelSettings; onSaved: (settings: ModelSettings) => void }) {

  return (
    <main className="setup-screen">
      <section className="setup-card">
        <div className="brand-mark">知命</div>
        <span className="eyebrow">开源桌面版 · 数据只在本机</span>
        <h1>先连接你的模型</h1>
        <p>选择模型服务的原生协议。API Key 将交给系统密钥库保管，不写入项目数据库。</p>
        <ModelSettingsFields initial={initial} submitLabel="保存并进入命册" onSaved={onSaved} />
        <div className="privacy-line"><span><Database size={15} />命册、对话、知识库和命例库均保存在本机</span><ZhimingLifeLink /></div>
      </section>
    </main>
  );
}

function PersonForm({ onClose, onCreated }: { onClose: () => void; onCreated: (person: Person) => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError("");
    const data = new FormData(event.currentTarget);
    try {
      const person = await api.createPerson({
        name: String(data.get("name")), relationship: String(data.get("relationship")),
        birth: { calendar: String(data.get("calendar")) as "solar" | "lunar", year: Number(data.get("birth_year")), month: Number(data.get("birth_month")), day: Number(data.get("birth_day")), hour: Number(data.get("hour")), gender: String(data.get("gender")) as "male" | "female", is_leap_month: false, birth_place: String(data.get("birth_place")) },
        notes: String(data.get("notes")),
      });
      onCreated(person);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "创建失败"); setBusy(false); }
  }
  return <Modal title="新录生辰" onClose={onClose}><form className="form-grid birth-form" onSubmit={submit}>
    <p className="form-preface span-2">一人一帖。先记下确定的生辰与事实，后续每次问命都归入此册。</p>
    <label className="span-2 manuscript-input">称呼<input name="name" placeholder="例如：我自己、母亲、林先生" required autoFocus /></label>
    <ChoiceField className="span-2" legend="关系" name="relationship" defaultValue="self" options={[{ value: "self", label: "自己" }, { value: "family", label: "家人" }, { value: "partner", label: "伴侣" }, { value: "friend", label: "朋友" }, { value: "client", label: "来访者" }, { value: "other", label: "其他" }]} />
    <ChoiceField legend="性别" name="gender" defaultValue="male" options={[{ value: "male", label: "男" }, { value: "female", label: "女" }]} />
    <ChoiceField legend="历法" name="calendar" defaultValue="solar" options={[{ value: "solar", label: "公历" }, { value: "lunar", label: "农历" }]} />
    <fieldset className="birth-date-line span-2"><legend>出生日期</legend><div><label>出生年份<input name="birth_year" type="number" min="1900" max="2100" placeholder="1990" required /></label><i>年</i><label>出生月份<input name="birth_month" type="number" min="1" max="12" placeholder="6" required /></label><i>月</i><label>出生日期<input name="birth_day" type="number" min="1" max="31" placeholder="15" required /></label><i>日</i></div></fieldset>
    <label>出生时辰<select name="hour" defaultValue="12">{Array.from({ length: 24 }, (_, hour) => <option key={hour} value={hour}>{String(hour).padStart(2, "0")}:00</option>)}</select></label>
    <label>出生地<input name="birth_place" placeholder="可留空" /></label>
    <label className="span-2">已知事实<textarea name="notes" placeholder="职业、家庭状态等，只记事实" /></label>
    {error && <p className="form-error span-2">{error}</p>}
    <div className="form-actions span-2"><button type="button" className="quiet-button" onClick={onClose}>取消</button><button className="primary-button" disabled={busy}>{busy ? <><LoaderCircle className="spin" size={15} />正在保存…</> : "保存命主"}</button></div>
  </form></Modal>;
}

function SessionForm({ person, persons, onClose, onCreated }: { person: Person; persons: Person[]; onClose: () => void; onCreated: (session: Session) => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(""); const data = new FormData(event.currentTarget);
    const secondary = String(data.get("secondary") || "");
    try {
      const result = await api.createSession({ primary_person_id: person.id, secondary_person_id: secondary || null, title: String(data.get("title")) });
      onCreated(result);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "创建咨询失败");
      setBusy(false);
    }
  }
  return <Modal title="新开一问" onClose={onClose}><form className="form-stack" onSubmit={submit}>
    <div className="person-context"><span className="person-seal">{person.name.slice(0, 1)}</span><div><strong>{person.name}</strong><small>系统将按问题自动采用八字分析</small></div></div>
    <label>这次想问什么<input name="title" placeholder="例如：今年事业是否适合调整" required autoFocus /></label>
    <label>加一位命主合看（可选）<select name="secondary" defaultValue=""><option value="">不添加</option>{persons.filter((item) => item.id !== person.id).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
    {error && <p className="form-error">{error}</p>}
    <div className="form-actions"><button type="button" className="quiet-button" onClick={onClose}>取消</button><button className="primary-button" disabled={busy}>{busy ? <><LoaderCircle className="spin" size={15} />正在创建咨询…</> : "进入咨询"}</button></div>
  </form></Modal>;
}

function LibraryManager({ statuses, onClose, onImported }: { statuses: LibraryStatus[]; onClose: () => void; onImported: () => Promise<void> }) {
  const [kind, setKind] = useState<LibraryKind>("knowledge");
  const [file, setFile] = useState<File | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [sources, setSources] = useState<LibrarySource[]>([]);
  const [loadingSources, setLoadingSources] = useState(true);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [notice, setNotice] = useState("");
  const current = statuses.find((item) => item.kind === kind);
  async function loadSources(target: LibraryKind) {
    setLoadingSources(true);
    try { setSources(await api.listLibrarySources(target)); }
    catch (reason) { setNotice(reason instanceof Error ? reason.message : "资料清单读取失败"); }
    finally { setLoadingSources(false); }
  }
  useEffect(() => { void loadSources(kind); }, [kind]);
  async function submit(event: FormEvent) {
    event.preventDefault(); if (!file) return; setBusy(true); setNotice("");
    try {
      const content = await file.text();
      const result = await api.importLibrary(kind, { title: file.name.replace(/\.[^.]+$/, ""), source_name: file.name, content, confirmed_anonymized: confirmed });
      setNotice(result.status === "duplicate" ? "内容已存在，无需重复导入" : "资料已导入并完成本地索引");
      await Promise.all([onImported(), loadSources(kind)]); setFile(null);
    } catch (reason) { setNotice(reason instanceof Error ? reason.message : "导入失败"); }
    finally { setBusy(false); }
  }
  async function removeSource(source: LibrarySource) {
    if (!window.confirm(`确定从${kind === "knowledge" ? "知识库" : "命例库"}删除《${source.title}》吗？`)) return;
    setDeletingId(source.id); setNotice("");
    try {
      await api.deleteLibrarySource(kind, source.id);
      await Promise.all([onImported(), loadSources(kind)]);
      setNotice("资料及其本地索引已删除");
    } catch (reason) { setNotice(reason instanceof Error ? reason.message : "删除失败"); }
    finally { setDeletingId(null); }
  }
  return <Modal title="本地资料库" onClose={onClose}><div className="library-tabs"><button className={kind === "knowledge" ? "active" : ""} onClick={() => { setKind("knowledge"); setConfirmed(false); }}>知识库</button><button className={kind === "cases" ? "active" : ""} onClick={() => setKind("cases")}>命例库</button></div>
    <div className="library-summary compact"><div><span>{current?.source_count ?? 0}</span>份资料</div><div><span>{current?.vector_backend ?? "准备中"}</span>检索引擎</div></div>
    <div className="library-explainer"><BookOpen size={20} /><div><strong>{kind === "knowledge" ? "用于存放经典、讲义与个人笔记" : "用于存放经过复盘的匿名咨询案例"}</strong><p>{kind === "knowledge" ? "当前支持 UTF-8 的 TXT、Markdown 文本；同名文件再次导入会替换旧版本。" : "命例库与知识库物理分离。仅导入去除姓名、电话、地址等身份信息后的内容。"}</p></div></div>
    <section className="source-section"><div className="source-heading"><span>资料名称与来源</span><small>{kind === "knowledge" ? "知识" : "匿名命例"}</small></div>{loadingSources ? <div className="source-loading" aria-live="polite"><LoaderCircle className="spin" size={15} />正在读取资料清单…</div> : sources.length ? <div className="source-list">{sources.map((source) => <article key={source.id}><div><strong>{source.title}</strong><small>{source.source_name} · {source.created_at.slice(0, 10)}</small></div><button type="button" className="source-delete" aria-label={`删除 ${source.title}`} disabled={deletingId !== null} onClick={() => void removeSource(source)}>{deletingId === source.id ? <LoaderCircle className="spin" size={15} /> : <Trash2 size={15} />}</button></article>)}</div> : <div className="source-empty">当前没有资料，可以从下方添加。</div>}</section>
    <form className="import-box" onSubmit={submit}><FileUp size={24} /><label className="file-picker"><input aria-label="选择资料文件" type="file" accept=".txt,.md,text/plain,text/markdown" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />{file ? file.name : "选择 TXT 或 Markdown 文件"}</label>
      {kind === "cases" && <label className="check-line"><input type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} />导入前确认已匿名化</label>}
      {notice && <p className="import-notice" aria-live="polite">{notice}</p>}<button className="primary-button" disabled={!file || busy || (kind === "cases" && !confirmed)}>{busy ? <><LoaderCircle className="spin" size={15} />正在解析并建立索引…</> : `导入到${kind === "knowledge" ? "知识库" : "命例库"}`}</button>{busy && <small className="operation-hint">文件越大耗时越长，请保持应用开启。</small>}
    </form>
  </Modal>;
}

function SettingsDialog({ settings, onClose, onSaved }: { settings: ModelSettings; onClose: () => void; onSaved: (value: ModelSettings) => void }) {
  return <Modal title="模型设置" onClose={onClose}><ModelSettingsFields initial={settings} submitLabel="保存设置" onSaved={onSaved} onCancel={onClose} /></Modal>;
}

export default function App() {
  const [loading, setLoading] = useState(true); const [error, setError] = useState("");
  const [settings, setSettings] = useState<ModelSettings | null>(null); const [persons, setPersons] = useState<Person[]>([]); const [activePersonId, setActivePersonId] = useState<string | null>(null);
  const [sessions, setSessions] = useState<Session[]>([]); const [activeSessionId, setActiveSessionId] = useState<string | null>(null); const [messages, setMessages] = useState<Message[]>([]);
  const [chart, setChart] = useState<Chart | null>(null); const [evidence, setEvidence] = useState<Evidence[]>([]); const [rightTab, setRightTab] = useState<"chart" | "evidence">("chart");
  const [libraries, setLibraries] = useState<LibraryStatus[]>([]); const [composer, setComposer] = useState(""); const [sending, setSending] = useState(false);
  const [modal, setModal] = useState<"person" | "session" | "library" | "settings" | null>(null);
  const activePerson = persons.find((item) => item.id === activePersonId) ?? null; const activeSession = sessions.find((item) => item.id === activeSessionId) ?? null;

  async function refreshLibraries() { setLibraries(await api.getLibraryStatuses()); }
  useEffect(() => { (async () => { try { const [modelSettings, loadedPersons, statuses] = await Promise.all([api.getModelSettings(), api.listPersons(), api.getLibraryStatuses()]); setSettings(modelSettings); setPersons(loadedPersons); setLibraries(statuses); setActivePersonId(loadedPersons[0]?.id ?? null); } catch (reason) { setError(reason instanceof Error ? reason.message : "无法连接本地服务"); } finally { setLoading(false); } })(); }, []);
  useEffect(() => { if (!activePersonId) { setSessions([]); setChart(null); return; } setActiveSessionId(null); setMessages([]); setEvidence([]); Promise.all([api.listSessions(activePersonId), api.getChart(activePersonId).catch(() => null)]).then(([items, nextChart]) => { setSessions(items); setChart(nextChart); }).catch((reason) => setError(reason.message)); }, [activePersonId]);

  async function openSession(session: Session) { setActiveSessionId(session.id); setMessages(await api.listMessages(session.id)); setEvidence([]); }
  async function submitMessage(event: FormEvent) { event.preventDefault(); if (!activeSession || !composer.trim()) return; const content = composer.trim(); setComposer(""); setSending(true); try { const result = await api.sendMessage(activeSession.id, content); setMessages((items) => [...items, result.user_message, result.assistant_message]); setEvidence(result.evidence); if (result.evidence.length) setRightTab("evidence"); } catch (reason) { setError(reason instanceof Error ? reason.message : "发送失败"); setComposer(content); } finally { setSending(false); } }

  const libraryReady = useMemo(() => libraries.some((item) => item.source_count > 0), [libraries]);
  if (loading) return <div className="loading-screen"><div className="brand-mark">知命</div><LoaderCircle className="spin" /><p>正在启动本地服务并准备资料…</p></div>;
  if (!settings) return <div className="service-error"><h1>本地服务未连接</h1><p>{error}</p><button className="primary-button" onClick={() => window.location.reload()}>重新连接</button></div>;
  if (!settings.has_api_key) return <ModelSetup initial={settings} onSaved={setSettings} />;

  return <div className="app-shell">
    <aside className="left-rail" aria-label="案上命册">
      <div className="brand-row"><div><span>知命</span><small>案上命册</small></div><button className="icon-button" onClick={() => setModal("settings")} aria-label="模型设置"><Settings size={17} /></button></div>
      <div className="rail-action"><button className="primary-button full" disabled={!activePerson} onClick={() => setModal("session")}><CirclePlus size={16} />新开一问</button></div>
      <div className="section-label"><span>命主</span><span>{persons.length} 位</span></div>
      <div className="person-list">{persons.map((person) => <button key={person.id} className={`person-row ${person.id === activePersonId ? "active" : ""}`} onClick={() => setActivePersonId(person.id)}><span className="person-seal">{person.name.slice(0, 1)}</span><span><strong>{person.name}</strong><small>{relationshipLabels[person.relationship] ?? person.relationship}</small></span><ChevronRight size={14} /></button>)}<button className="add-person" onClick={() => setModal("person")}><UserRoundPlus size={15} />新增命主</button></div>
      {activePerson && <><div className="section-label history-label"><span>{activePerson.name} · 历来之问</span><span>{sessions.length}</span></div><div className="session-list">{sessions.map((session) => <button key={session.id} className={session.id === activeSessionId ? "active" : ""} aria-label={session.title} onClick={() => openSession(session)}><MessageSquareText size={14} /><span><strong>{session.title}</strong><small>八字 · {session.updated_at.slice(0, 10)}</small></span></button>)}</div></>}
      <div className="rail-footer"><div className="library-row"><button onClick={() => setModal("library")} aria-label="资料库"><Library size={16} /><span><strong>资料库</strong><small>{libraryReady ? "本地检索已就绪" : "等待导入资料"}</small></span></button><span className={libraryReady ? "status-dot ready" : "status-dot"} /></div><ZhimingLifeLink compact /></div>
    </aside>

    <main className="consultation-pane" aria-label="桌前问命">
      <header className="pane-header"><div><span className="eyebrow">{activeSession ? "八 字 咨 询" : "命 主 概 览"}</span><h1>{activeSession?.title ?? activePerson?.name ?? "命册尚空"}</h1>{activePerson && <p>正在看：{activePerson.name}{activePerson.birth ? ` · ${activePerson.birth.calendar === "solar" ? "公历" : "农历"} ${activePerson.birth.year} 年生` : " · 待补生辰"}</p>}</div>{activePerson && <button className="outline-button" onClick={() => setModal("session")}><UsersRound size={15} />新开一问</button>}</header>
      {!activePerson ? <section className="empty-state"><div className="empty-seal">命</div><h2>先建立第一份命册</h2><p>录入命主与出生信息，后续咨询、命盘和记录都会明确归到这个人。</p><button className="primary-button" onClick={() => setModal("person")}><UserRoundPlus size={16} />新增命主</button></section> : activeSession ? <>
        <section className="message-stream">{messages.length === 0 && <div className="conversation-opening"><span className="eyebrow">开 卷</span><h2>{activeSession.title}</h2><p>直接说具体困惑。系统会结合命盘、本地知识和匿名命例回答。</p></div>}{messages.map((message) => message.role !== "system" && <article key={message.id} className={`message ${message.role}`}><span>{message.role === "assistant" ? "命师回话" : activePerson.name}</span><div>{message.content}</div></article>)}{sending && <article className="message assistant pending" aria-live="polite"><span>命师回话</span><div><LoaderCircle className="spin" size={18} />正在检索、重排依据并生成解读，可能需要一些时间…</div></article>}</section>
        <form className="composer" onSubmit={submitMessage}><textarea value={composer} onChange={(event) => setComposer(event.target.value)} placeholder="继续问这件事……" onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); event.currentTarget.form?.requestSubmit(); } }} /><button className="send-button" aria-label="发送" disabled={sending || !composer.trim()}><Send size={17} /></button><small>Enter 发送 · Shift + Enter 换行</small></form>
      </> : <section className="overview"><div className="overview-intro"><span className="eyebrow">一 人 一 册</span><h2>从这份命册，开始一段有来有回的咨询。</h2><p>出生信息用于确定性排盘；模型负责结合问题、知识和匿名命例进行解读。</p><button className="primary-button" onClick={() => setModal("session")}><CirclePlus size={16} />新开一问</button></div><div className="overview-grid"><div><span>既往咨询</span><strong>{sessions.length}</strong></div><div><span>已录事实</span><strong>{activePerson.notes ? "有" : "—"}</strong></div><div><span>本地资料</span><strong>{libraries.reduce((sum, item) => sum + item.source_count, 0)}</strong></div></div>{sessions.length > 0 && <div className="recent-block"><span className="eyebrow">最 近</span>{sessions.slice(0, 3).map((session) => <button key={session.id} onClick={() => openSession(session)}><span>{session.title}</span><ChevronRight size={15} /></button>)}</div>}</section>}
    </main>

    <aside className="right-panel" aria-label="命造档案"><header><div><span className="eyebrow">命 造 档 案</span><h2>{activePerson?.name ?? "未选择"}</h2></div><PanelRightClose size={18} aria-hidden="true" /></header><div className="right-tabs"><button className={rightTab === "chart" ? "active" : ""} onClick={() => setRightTab("chart")}>命盘</button><button className={rightTab === "evidence" ? "active" : ""} onClick={() => setRightTab("evidence")}>依据 {evidence.length ? `· ${evidence.length}` : ""}</button></div>
      <div className="right-content">{rightTab === "chart" ? chart ? <><div className="chart-label">四 柱</div><div className="pillars">{[chart.year, chart.month, chart.day, chart.hour].map((pillar, index) => <div key={index}><strong>{pillar[0]}</strong><span>{pillar[1]}</span><small>{["年", "月", "日", "时"][index]}</small></div>)}</div><div className="detail-row"><span>日主</span><strong>{chart.day_master} · {chart.day_master_wuxing}</strong></div><div className="wuxing-row">{Object.entries(chart.wuxing_counts).map(([name, count]) => <div key={name}><span>{name}</span><i style={{ height: `${Math.max(10, count * 14)}px` }} /><small>{count}</small></div>)}</div>{activePerson?.notes && <div className="notes-card"><span className="eyebrow">已 知 事 实</span><p>{activePerson.notes}</p></div>}</> : <div className="right-empty"><div>未完成排盘</div><p>请检查出生日期与时辰。</p></div> : evidence.length ? <div className="evidence-list">{evidence.map((item, index) => <article key={`${item.source_id}-${item.position}`}><span>{item.library_kind === "knowledge" ? "知识" : "匿名命例"} · {index + 1}</span><h3>{item.title}</h3><p>{item.content}</p><small>{item.source_name}</small></article>)}</div> : <div className="right-empty"><div>暂无引用依据</div><p>发送问题后，这里会展示本轮实际检索到的本地资料。</p></div>}</div>
    </aside>
    {error && <button className="error-toast" onClick={() => setError("")}>{error}<X size={14} /></button>}
    {modal === "person" && <PersonForm onClose={() => setModal(null)} onCreated={(person) => { setPersons((items) => [person, ...items]); setActivePersonId(person.id); setModal(null); }} />}
    {modal === "session" && activePerson && <SessionForm person={activePerson} persons={persons} onClose={() => setModal(null)} onCreated={(session) => { setSessions((items) => [session, ...items]); setModal(null); openSession(session); }} />}
    {modal === "library" && <LibraryManager statuses={libraries} onClose={() => setModal(null)} onImported={refreshLibraries} />}
    {modal === "settings" && <SettingsDialog settings={settings} onClose={() => setModal(null)} onSaved={(value) => { setSettings(value); setModal(null); }} />}
  </div>;
}
