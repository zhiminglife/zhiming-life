import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";
import * as api from "./api";

vi.mock("./api", () => ({
  getModelSettings: vi.fn(),
  saveModelSettings: vi.fn(),
  testModelSettings: vi.fn(),
  listPersons: vi.fn(),
  createPerson: vi.fn(),
  listSessions: vi.fn(),
  createSession: vi.fn(),
  listMessages: vi.fn(),
  sendMessage: vi.fn(),
  getChart: vi.fn(),
  getLibraryStatuses: vi.fn(),
  importLibrary: vi.fn(),
  listLibrarySources: vi.fn(),
  deleteLibrarySource: vi.fn(),
}));

const person = {
  id: "p1",
  name: "我自己",
  relationship: "self",
  birth: {
    calendar: "solar" as const,
    year: 1990,
    month: 6,
    day: 15,
    hour: 14,
    gender: "male" as const,
    is_leap_month: false,
    birth_place: "",
  },
  notes: "",
  created_at: "2026-08-01",
  updated_at: "2026-08-01",
};

const partner = {
  ...person,
  id: "p2",
  name: "周女士",
  relationship: "partner",
  birth: { ...person.birth, year: 1992, month: 9, day: 8, hour: 9, gender: "female" as const },
};

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.listPersons).mockResolvedValue([]);
  vi.mocked(api.listSessions).mockResolvedValue([]);
  vi.mocked(api.getLibraryStatuses).mockResolvedValue([
    { kind: "knowledge", path: "knowledge.sqlite", source_count: 0, chunk_count: 0, vector_backend: "python" },
    { kind: "cases", path: "cases.sqlite", source_count: 0, chunk_count: 0, vector_backend: "python" },
  ]);
  vi.mocked(api.listLibrarySources).mockResolvedValue([]);
  vi.mocked(api.deleteLibrarySource).mockResolvedValue(undefined);
});

describe("App", () => {
  it("shows model setup before entering the workspace", async () => {
    vi.mocked(api.getModelSettings).mockResolvedValue({
      base_url: "https://api.deepseek.com/v1",
      model: "deepseek-chat",
      has_api_key: false,
    });

    render(<App />);

    expect(await screen.findByRole("heading", { name: "先连接你的模型" })).toBeInTheDocument();
    expect(screen.getByLabelText("API Key")).toHaveAttribute("type", "password");
  });

  it("shows connection progress while validating model settings", async () => {
    const user = userEvent.setup();
    let finishTest: (value: { status: string }) => void = () => undefined;
    vi.mocked(api.getModelSettings).mockResolvedValue({
      base_url: "https://api.deepseek.com/v1",
      model: "deepseek-chat",
      has_api_key: false,
    });
    vi.mocked(api.saveModelSettings).mockResolvedValue({
      base_url: "https://api.deepseek.com/v1",
      model: "deepseek-chat",
      has_api_key: true,
    });
    vi.mocked(api.testModelSettings).mockImplementation(() => new Promise((resolve) => { finishTest = resolve; }));

    render(<App />);
    await user.type(await screen.findByLabelText("API Key"), "test-key");
    await user.click(screen.getByRole("button", { name: "保存并进入命册" }));

    expect(await screen.findByText("正在测试模型连接…")).toBeInTheDocument();
    expect(api.testModelSettings).toHaveBeenCalledOnce();
    finishTest({ status: "ok" });
    expect(await screen.findByText("先建立第一份命册")).toBeInTheDocument();
  });

  it("opens the three-column person workspace", async () => {
    vi.mocked(api.getModelSettings).mockResolvedValue({
      base_url: "https://api.deepseek.com/v1",
      model: "deepseek-chat",
      has_api_key: true,
    });
    vi.mocked(api.listPersons).mockResolvedValue([person]);
    vi.mocked(api.getChart).mockResolvedValue({
      year: "庚午", month: "壬午", day: "辛亥", hour: "乙未",
      day_master: "辛", day_master_wuxing: "金",
      wuxing_counts: { 木: 1, 火: 2, 土: 1, 金: 1, 水: 3 }, rendered: "",
    });

    render(<App />);

    expect((await screen.findAllByText("我自己")).length).toBeGreaterThan(0);
    expect(await screen.findByText("四 柱")).toBeInTheDocument();
    expect(screen.getByText(/辛 · 金/)).toBeInTheDocument();
    expect(screen.getAllByText("新开一问").length).toBeGreaterThan(0);
  });

  it("creates a person with the complete birth profile", async () => {
    const user = userEvent.setup();
    vi.mocked(api.getModelSettings).mockResolvedValue({
      base_url: "https://api.deepseek.com/v1", model: "deepseek-chat", has_api_key: true,
    });
    vi.mocked(api.createPerson).mockResolvedValue(partner);
    vi.mocked(api.getChart).mockRejectedValue(new Error("not needed"));

    render(<App />);
    await user.click((await screen.findAllByRole("button", { name: "新增命主" }))[0]);
    await user.type(screen.getByLabelText("称呼"), "周女士");
    await user.selectOptions(screen.getByLabelText("关系"), "partner");
    await user.selectOptions(screen.getByLabelText("性别"), "female");
    await user.selectOptions(screen.getByLabelText("历法"), "solar");
    await user.type(screen.getByLabelText("出生日期"), "1992-09-08");
    await user.selectOptions(screen.getByLabelText("出生时辰"), "9");
    await user.type(screen.getByLabelText("出生地"), "上海");
    await user.type(screen.getByLabelText("已知事实"), "目前从事产品工作");
    await user.click(screen.getByRole("button", { name: "保存命主" }));

    await waitFor(() => expect(api.createPerson).toHaveBeenCalledWith({
      name: "周女士",
      relationship: "partner",
      birth: {
        calendar: "solar", year: 1992, month: 9, day: 8, hour: 9,
        gender: "female", is_leap_month: false, birth_place: "上海",
      },
      notes: "目前从事产品工作",
    }));
    expect((await screen.findAllByText("周女士")).length).toBeGreaterThan(0);
  });

  it("creates a consultation with a secondary person", async () => {
    const user = userEvent.setup();
    vi.mocked(api.getModelSettings).mockResolvedValue({
      base_url: "https://api.deepseek.com/v1", model: "deepseek-chat", has_api_key: true,
    });
    vi.mocked(api.listPersons).mockResolvedValue([person, partner]);
    vi.mocked(api.getChart).mockRejectedValue(new Error("not needed"));
    vi.mocked(api.listMessages).mockResolvedValue([]);
    vi.mocked(api.createSession).mockResolvedValue({
      id: "s-together", primary_person_id: "p1", secondary_person_id: "p2",
      title: "事业调整与伴侣共同规划", created_at: "2026-08-01", updated_at: "2026-08-01",
    });

    render(<App />);
    await user.click((await screen.findAllByRole("button", { name: "新开一问" }))[0]);
    await user.type(screen.getByLabelText("这次想问什么"), "事业调整与伴侣共同规划");
    await user.selectOptions(screen.getByLabelText("加一位命主合看（可选）"), "p2");
    await user.click(screen.getByRole("button", { name: "进入咨询" }));

    await waitFor(() => expect(api.createSession).toHaveBeenCalledWith({
      primary_person_id: "p1",
      secondary_person_id: "p2",
      title: "事业调整与伴侣共同规划",
    }));
    expect(await screen.findByText("直接说具体困惑。系统会结合命盘、本地知识和匿名命例回答。")).toBeInTheDocument();
  });

  it("updates model settings from the workspace", async () => {
    const user = userEvent.setup();
    vi.mocked(api.getModelSettings).mockResolvedValue({
      base_url: "https://api.deepseek.com/v1", model: "deepseek-chat", has_api_key: true,
    });
    vi.mocked(api.saveModelSettings).mockResolvedValue({
      base_url: "https://gateway.example/v1", model: "custom-model", has_api_key: true,
    });
    vi.mocked(api.testModelSettings).mockResolvedValue({ status: "ok" });

    render(<App />);
    await user.click(await screen.findByRole("button", { name: "模型设置" }));
    const dialog = screen.getByRole("dialog", { name: "模型设置" });
    const baseUrl = within(dialog).getByLabelText("接口地址");
    const model = within(dialog).getByLabelText("模型名称");
    await user.clear(baseUrl);
    await user.type(baseUrl, "https://gateway.example/v1");
    await user.clear(model);
    await user.type(model, "custom-model");
    await user.click(within(dialog).getByRole("button", { name: "保存设置" }));

    await waitFor(() => expect(api.saveModelSettings).toHaveBeenCalledWith({
      base_url: "https://gateway.example/v1", model: "custom-model", api_key: undefined,
    }));
    expect(api.testModelSettings).toHaveBeenCalledOnce();
  });

  it("switches between knowledge and anonymized case imports", async () => {
    const user = userEvent.setup();
    vi.mocked(api.getModelSettings).mockResolvedValue({
      base_url: "https://api.deepseek.com/v1",
      model: "deepseek-chat",
      has_api_key: true,
    });
    vi.mocked(api.listPersons).mockResolvedValue([person]);
    vi.mocked(api.getChart).mockRejectedValue(new Error("not needed"));

    render(<App />);
    await user.click(await screen.findByRole("button", { name: "资料库" }));
    await user.click(screen.getByRole("button", { name: "命例库" }));

    expect(screen.getByText("导入前确认已匿名化")).toBeInTheDocument();
  });

  it("requires anonymization confirmation before importing a case", async () => {
    const user = userEvent.setup();
    vi.mocked(api.getModelSettings).mockResolvedValue({
      base_url: "https://api.deepseek.com/v1", model: "deepseek-chat", has_api_key: true,
    });
    vi.mocked(api.listPersons).mockResolvedValue([person]);
    vi.mocked(api.getChart).mockRejectedValue(new Error("not needed"));
    vi.mocked(api.importLibrary).mockResolvedValue({ source_id: "case-1", status: "inserted", chunk_count: 1 });

    render(<App />);
    await user.click(await screen.findByRole("button", { name: "资料库" }));
    await user.click(screen.getByRole("button", { name: "命例库" }));
    const file = new File(["匿名命例内容"], "career-case.md", { type: "text/markdown" });
    Object.defineProperty(file, "text", { value: () => Promise.resolve("匿名命例内容") });
    await user.upload(screen.getByLabelText("选择资料文件"), file);
    expect(screen.getByRole("button", { name: "导入到命例库" })).toBeDisabled();
    await user.click(screen.getByText("导入前确认已匿名化"));
    await user.click(screen.getByRole("button", { name: "导入到命例库" }));

    await waitFor(() => expect(api.importLibrary).toHaveBeenCalledWith("cases", {
      title: "career-case", source_name: "career-case.md", content: "匿名命例内容", confirmed_anonymized: true,
    }));
  });

  it("shows attributed library sources and deletes a selected source", async () => {
    const user = userEvent.setup();
    vi.mocked(api.getModelSettings).mockResolvedValue({
      base_url: "https://api.deepseek.com/v1",
      model: "deepseek-chat",
      has_api_key: true,
    });
    vi.mocked(api.listPersons).mockResolvedValue([person]);
    vi.mocked(api.getChart).mockRejectedValue(new Error("not needed"));
    vi.mocked(api.listLibrarySources).mockResolvedValue([{
      id: "source-1",
      title: "事业与关系咨询的分析框架",
      source_name: "知命内置知识 · 原创整理 · v1.1",
      chunk_count: 3,
      created_at: "2026-08-01T00:00:00+00:00",
    }]);
    vi.spyOn(window, "confirm").mockReturnValue(true);

    render(<App />);
    await user.click(await screen.findByRole("button", { name: "资料库" }));

    expect(await screen.findByText("事业与关系咨询的分析框架")).toBeInTheDocument();
    expect(screen.getByText(/知命内置知识 · 原创整理 · v1\.1/)).toBeInTheDocument();
    expect(screen.queryByText("3 个片段")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "删除 事业与关系咨询的分析框架" }));

    await waitFor(() => expect(api.deleteLibrarySource).toHaveBeenCalledWith("knowledge", "source-1"));
  });

  it("shows indexing progress while importing a library file", async () => {
    const user = userEvent.setup();
    let finishImport: (value: { source_id: string; status: string; chunk_count: number }) => void = () => undefined;
    vi.mocked(api.getModelSettings).mockResolvedValue({
      base_url: "https://api.deepseek.com/v1",
      model: "deepseek-chat",
      has_api_key: true,
    });
    vi.mocked(api.listPersons).mockResolvedValue([person]);
    vi.mocked(api.getChart).mockRejectedValue(new Error("not needed"));
    vi.mocked(api.importLibrary).mockImplementation(() => new Promise((resolve) => { finishImport = resolve; }));

    render(<App />);
    await user.click(await screen.findByRole("button", { name: "资料库" }));
    const file = new File(["事业资料"], "career.md", { type: "text/markdown" });
    Object.defineProperty(file, "text", { value: () => Promise.resolve("事业资料") });
    await user.upload(screen.getByLabelText("选择资料文件"), file);
    await user.click(screen.getByRole("button", { name: "导入到知识库" }));

    expect(await screen.findByText("正在解析并建立索引…")).toBeInTheDocument();
    expect(screen.getByText("文件越大耗时越长，请保持应用开启。")).toBeInTheDocument();
    finishImport({ source_id: "s1", status: "inserted", chunk_count: 1 });
    expect(await screen.findByText("资料已导入并完成本地索引")).toBeInTheDocument();
  });

  it("sends a message in an existing consultation", async () => {
    const user = userEvent.setup();
    vi.mocked(api.getModelSettings).mockResolvedValue({
      base_url: "https://api.deepseek.com/v1",
      model: "deepseek-chat",
      has_api_key: true,
    });
    vi.mocked(api.listPersons).mockResolvedValue([person]);
    vi.mocked(api.listSessions).mockResolvedValue([{
      id: "s1", primary_person_id: "p1", secondary_person_id: null,
      title: "今年事业", created_at: "2026-08-01", updated_at: "2026-08-01",
    }]);
    vi.mocked(api.listMessages).mockResolvedValue([]);
    vi.mocked(api.getChart).mockRejectedValue(new Error("not needed"));
    vi.mocked(api.sendMessage).mockResolvedValue({
      user_message: { id: 1, session_id: "s1", role: "user", content: "今年事业如何？", created_at: "" },
      assistant_message: { id: 2, session_id: "s1", role: "assistant", content: "先看事业节奏。", created_at: "" },
      evidence: [],
    });

    render(<App />);
    await waitFor(() => expect(screen.getAllByRole("button", { name: /今年事业/ }).length).toBeGreaterThan(0));
    await user.click(screen.getAllByRole("button", { name: /今年事业/ })[0]);
    await user.type(screen.getByPlaceholderText("继续问这件事……"), "今年事业如何？");
    await user.click(screen.getByRole("button", { name: "发送" }));

    await waitFor(() => expect(api.sendMessage).toHaveBeenCalledWith("s1", "今年事业如何？"));
    expect(await screen.findByText("先看事业节奏。")).toBeInTheDocument();
  });

  it("loads consultation history and shows retrieved evidence", async () => {
    const user = userEvent.setup();
    vi.mocked(api.getModelSettings).mockResolvedValue({
      base_url: "https://api.deepseek.com/v1", model: "deepseek-chat", has_api_key: true,
    });
    vi.mocked(api.listPersons).mockResolvedValue([person]);
    vi.mocked(api.listSessions).mockResolvedValue([{
      id: "s1", primary_person_id: "p1", secondary_person_id: null,
      title: "今年事业", created_at: "2026-08-01", updated_at: "2026-08-01",
    }]);
    vi.mocked(api.listMessages).mockResolvedValue([
      { id: 1, session_id: "s1", role: "user", content: "之前的问题", created_at: "" },
      { id: 2, session_id: "s1", role: "assistant", content: "之前的回复", created_at: "" },
    ]);
    vi.mocked(api.getChart).mockRejectedValue(new Error("not needed"));
    vi.mocked(api.sendMessage).mockResolvedValue({
      user_message: { id: 3, session_id: "s1", role: "user", content: "继续分析", created_at: "" },
      assistant_message: { id: 4, session_id: "s1", role: "assistant", content: "结合本地资料回答", created_at: "" },
      evidence: [{
        library_kind: "knowledge", source_id: "k1", source_name: "原创整理",
        title: "事业分析框架", position: 0, content: "先看现实条件。", score: 1,
      }],
    });

    render(<App />);
    await user.click((await screen.findAllByRole("button", { name: /今年事业/ }))[0]);
    expect(await screen.findByText("之前的回复")).toBeInTheDocument();
    await user.type(screen.getByPlaceholderText("继续问这件事……"), "继续分析");
    await user.click(screen.getByRole("button", { name: "发送" }));

    expect(await screen.findByText("结合本地资料回答")).toBeInTheDocument();
    expect(screen.getByText("事业分析框架")).toBeInTheDocument();
    expect(screen.getByText("原创整理")).toBeInTheDocument();
  });

  it("recovers from a failed consultation creation instead of staying busy", async () => {
    const user = userEvent.setup();
    vi.mocked(api.getModelSettings).mockResolvedValue({
      base_url: "https://api.deepseek.com/v1",
      model: "deepseek-chat",
      has_api_key: true,
    });
    vi.mocked(api.listPersons).mockResolvedValue([person]);
    vi.mocked(api.getChart).mockRejectedValue(new Error("not needed"));
    vi.mocked(api.createSession).mockRejectedValue(new Error("创建咨询失败"));

    render(<App />);
    await user.click((await screen.findAllByRole("button", { name: "新开一问" }))[0]);
    await user.type(screen.getByLabelText("这次想问什么"), "事业调整");
    await user.click(screen.getByRole("button", { name: "进入咨询" }));

    expect(await screen.findByText("创建咨询失败")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "进入咨询" })).toBeEnabled();
  });
});
