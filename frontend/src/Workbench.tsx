import { useEffect, useRef, useState } from "react";
import {
  Alert,
  Button,
  Drawer,
  Dropdown,
  Empty,
  Input,
  Modal,
  Popconfirm,
  Spin,
  Table,
  Tabs,
  Tag,
  Tooltip,
  message,
} from "antd";
import {
  BarChartOutlined,
  PlusOutlined,
  MessageOutlined,
  StarOutlined,
  StarFilled,
  DatabaseOutlined,
  SettingOutlined,
  LogoutOutlined,
  MoreOutlined,
  ArrowUpOutlined,
  StopOutlined,
  ArrowRightOutlined,
  CheckCircleOutlined,
  LineChartOutlined,
  PieChartOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  SearchOutlined,
  ApartmentOutlined,
  HistoryOutlined,
  ReloadOutlined,
  ControlOutlined,
  ExclamationCircleOutlined,
  AudioOutlined,
  LoadingOutlined,
} from "@ant-design/icons";
import { api, post } from "./api";

import type { Msg } from "./types";
import Answer from "./QueryAnswer";
import QuickQuestions from "./QuickQuestions";
import WorkbenchSettingsPanel from "./WorkbenchSettings";
import FeedbackManagement from "./FeedbackManagement";
import {
  DEFAULT_WORKBENCH_SETTINGS,
  type CommonQuestion,
  type WorkbenchSettings,
} from "./workbenchConfig";

// 等待回答时按真实处理阶段轮换提示，避免长时间显示不变的技术步骤。
const THINKING_COPY: Record<string, string[]> = {
  理解问题: [
    "正在识别指标、时间范围和筛选条件",
    "正在匹配业务口径与相关数据表",
  ],
  执行取数: [
    "正在组织查询逻辑并校验取数范围",
    "正在查询数据，请稍候",
  ],
  整理结果: [
    "正在核对查询结果与关键数值",
    "正在整理分析结论和展示内容",
  ],
};

// 公网 IP 的 HTTP 页面不属于安全上下文，部分浏览器不会提供 randomUUID。
// 消息提交后会由后端返回正式 ID；这里仅生成前端渲染期间使用的临时唯一键。
function createClientMessageId() {
  if (typeof globalThis.crypto?.randomUUID === "function") {
    return globalThis.crypto.randomUUID();
  }
  if (typeof globalThis.crypto?.getRandomValues === "function") {
    const bytes = globalThis.crypto.getRandomValues(new Uint8Array(16));
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    const hex = Array.from(bytes, (value) => value.toString(16).padStart(2, "0"));
    return `${hex.slice(0, 4).join("")}-${hex.slice(4, 6).join("")}-${hex.slice(6, 8).join("")}-${hex.slice(8, 10).join("")}-${hex.slice(10).join("")}`;
  }
  return `message-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export default function Workbench({
  user,
  onLogout,
}: {
  user: any;
  onLogout: () => void;
}) {
  const [page, setPage] = useState<"ask" | "settings" | "feedback">("ask"),
    [catalog, setCatalog] = useState<any>(null),
    [workbenchSettings, setWorkbenchSettings] = useState<WorkbenchSettings>(
      DEFAULT_WORKBENCH_SETTINGS,
    ),
    [commonQuestions, setCommonQuestions] = useState<CommonQuestion[]>([]),
    [quickOpen, setQuickOpen] = useState(false),
    [questionOffset, setQuestionOffset] = useState(0),
    [conversations, setConversations] = useState<any[]>([]),
    [cid, setCid] = useState<string | null>(null),
    [msgs, setMsgs] = useState<Msg[]>([]),
    [input, setInput] = useState(""),
    [busy, setBusy] = useState(false),
    [stage, setStage] = useState(""),
    [thinkingIndex, setThinkingIndex] = useState(0),
    [drawer, setDrawer] = useState(""),
    [favorites, setFavorites] = useState<any[]>([]),
    [search, setSearch] = useState(""),
    [error, setError] = useState(""),
    [collapsed, setCollapsed] = useState(false),
    [feedback, setFeedback] = useState(""),
    [remark, setRemark] = useState(""),
    [rename, setRename] = useState<any>(null),
    [renameText, setRenameText] = useState(""),
    [testing, setTesting] = useState(false),
    [loadingChat, setLoadingChat] = useState(false),
    [recording, setRecording] = useState(false),
    [transcribing, setTranscribing] = useState(false);
  const abort = useRef<AbortController | null>(null),
    end = useRef<HTMLDivElement>(null),
    sending = useRef(false),
    recorder = useRef<MediaRecorder | null>(null),
    recordingStream = useRef<MediaStream | null>(null),
    recordingChunks = useRef<Blob[]>([]);
  const refresh = () => api("/conversations").then(setConversations);
  const refreshCommonQuestions = () =>
    api("/common-questions").then(setCommonQuestions);
  useEffect(() => {
    Promise.all([
      api("/catalog").then(setCatalog),
      api("/workbench/settings").then(setWorkbenchSettings),
      refreshCommonQuestions(),
      refresh(),
      api("/favorites").then(setFavorites),
    ]).catch((e) => setError(e.message));
  }, []);
  useEffect(() => {
    end.current?.scrollIntoView({ behavior: "smooth" });
  }, [msgs, stage, thinkingIndex]);
  useEffect(() => {
    if (!busy) return;
    setThinkingIndex(0);
    const timer = window.setInterval(
      () => setThinkingIndex((current) => current + 1),
      2400,
    );
    return () => window.clearInterval(timer);
  }, [busy, stage]);
  useEffect(
    () => () => {
      recorder.current?.stop();
      recordingStream.current?.getTracks().forEach((track) => track.stop());
    },
    [],
  );

  async function toggleRecording() {
    if (recording) {
      recorder.current?.stop();
      return;
    }
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      message.warning("当前页面无法使用麦克风，请通过 HTTPS 或 localhost 访问");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const preferredTypes = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"];
      const mimeType = preferredTypes.find((type) => MediaRecorder.isTypeSupported(type));
      const nextRecorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      recorder.current = nextRecorder;
      recordingStream.current = stream;
      recordingChunks.current = [];
      nextRecorder.ondataavailable = (event) => {
        if (event.data.size) recordingChunks.current.push(event.data);
      };
      nextRecorder.onerror = () => message.error("录音失败，请检查麦克风权限");
      nextRecorder.onstop = async () => {
        setRecording(false);
        stream.getTracks().forEach((track) => track.stop());
        recordingStream.current = null;
        const blob = new Blob(recordingChunks.current, {
          type: nextRecorder.mimeType || "audio/webm",
        });
        if (!blob.size) return;
        setTranscribing(true);
        try {
          const response = await fetch("/api/audio/transcribe", {
            method: "POST",
            headers: { "Content-Type": blob.type },
            body: blob,
          });
          if (!response.ok) {
            const data = await response.json().catch(() => ({}));
            throw new Error(data.detail || "语音识别失败");
          }
          const data = await response.json();
          setInput((current) => (current.trim() ? `${current.trim()} ${data.text}` : data.text));
          message.success("语音已转换为文字");
        } catch (error) {
          message.error((error as Error).message);
        } finally {
          setTranscribing(false);
          recorder.current = null;
          recordingChunks.current = [];
        }
      };
      nextRecorder.start();
      setRecording(true);
    } catch (error) {
      message.error((error as DOMException).name === "NotAllowedError" ? "请允许浏览器使用麦克风" : "无法启动录音");
    }
  }
  async function loadConversation(id: string) {
    if (sending.current) return;
    setPage("ask");
    setLoadingChat(true);
    setError("");
    try {
      const c = await api("/conversations/" + id);
      setCid(id);
      setMsgs(c.messages);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoadingChat(false);
    }
  }
  async function ask(question = input) {
    if (sending.current || !question.trim()) return;
    if (question === "__retry__") {
      question =
        [...msgs].reverse().find((m) => m.role === "user")?.content || "";
      if (!question) return;
    }
    sending.current = true;
    setBusy(true);
    setInput("");
    setError("");
    setStage("理解问题");
    setThinkingIndex(0);
    const controller = new AbortController();
    abort.current = controller;
    let id = cid;
    try {
      if (!id) {
        const c = await post("/conversations");
        id = c.id;
        setCid(id);
      }
      setMsgs((m) => [
        ...m,
        { id: createClientMessageId(), role: "user", content: question },
      ]);
      const res = await fetch("/api/conversations/" + id + "/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
        signal: controller.signal,
      });
      if (!res.ok) {
        const d = await res.json();
        throw new Error(d.detail || "问数失败");
      }
      const reader = res.body!.getReader(),
        decoder = new TextDecoder();
      let buffer = "";
      let gotResult = false;
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";
        for (const line of lines) {
          if (!line.trim()) continue;
          const event = JSON.parse(line);
          if (event.type === "status") {
            setStage(event.stage);
          }
          if (event.type === "result") {
            gotResult = true;
            setMsgs((m) => [...m, event.message]);
          }
        }
      }
      if (!gotResult) throw new Error("连接中断，未收到完整结果，请重试");
    } catch (e) {
      if ((e as Error).name === "AbortError") {
        setMsgs((m) => [
          ...m,
          {
            id: createClientMessageId(),
            role: "assistant",
            content: "本次生成已停止。",
            result: { status: "cancelled" },
          },
        ]);
      } else {
        setError((e as Error).message);
        setInput(question);
      }
    } finally {
      sending.current = false;
      setBusy(false);
      abort.current = null;
      refresh().catch(() => {});
      refreshCommonQuestions().catch(() => {});
    }
  }
  const saveWorkbenchSettings = async (
    values: Partial<WorkbenchSettings>,
  ) => {
    const updated = await api("/workbench/settings", {
      method: "PATCH",
      body: JSON.stringify(values),
    });
    setWorkbenchSettings(updated);
    if ("starter_questions" in values) setQuestionOffset(0);
    setCatalog((current: any) =>
      current
        ? { ...current, model: { ...current.model, name: updated.llm_model } }
        : current,
    );
    if (
      "common_questions_enabled" in values ||
      "common_question_threshold" in values
    ) {
      setCommonQuestions(await api("/common-questions"));
    }
  };
  const questionPool = Array.from(
    new Set([
      ...workbenchSettings.starter_questions,
      ...(catalog?.examples || []),
    ]),
  );
  const visibleStarterQuestions = Array.from(
    { length: Math.min(6, questionPool.length) },
    (_, index) => questionPool[(questionOffset + index) % questionPool.length],
  );
  const favorite = async (q: string) => {
    try {
      const saved = favorites.find((item) => item.question === q);
      if (saved) {
        await api("/favorites/" + saved.id, { method: "DELETE" });
      } else {
        await post("/favorites", { question: q });
      }
      setFavorites(await api("/favorites"));
      message.success(saved ? "已取消收藏" : "已收藏问题");
    } catch (e) {
      message.error((e as Error).message);
    }
  };
  const removeFavorite = async (id: number) => {
    await api("/favorites/" + id, { method: "DELETE" });
    setFavorites(await api("/favorites"));
    message.success("已取消收藏");
  };
  const removeCommonQuestion = async (id: number) => {
    await api("/common-questions/" + id, { method: "DELETE" });
    setCommonQuestions(await api("/common-questions"));
    message.success("已删除常见问题");
  };
  const handleConversationAction = (c: any, key: string) => {
    if (key === "pin") {
      api("/conversations/" + c.id, {
        method: "PATCH",
        body: JSON.stringify({ pinned: !c.pinned }),
      })
        .then(refresh)
        .catch((e) => message.error(e.message));
      return;
    }
    if (key === "rename") {
      setRename(c);
      setRenameText(c.title);
      return;
    }
    if (key === "delete") {
      api("/conversations/" + c.id, { method: "DELETE" })
        .then(async () => {
          if (cid === c.id) {
            setCid(null);
            setMsgs([]);
          }
          await refresh();
          message.success("会话已删除");
        })
        .catch((e) => message.error(e.message));
    }
  };
  const actions = (c: any) => [
    {
      key: "pin",
      label: c.pinned ? "取消置顶" : "置顶",
    },
    {
      key: "rename",
      label: "重命名",
    },
    {
      key: "delete",
      label: "删除会话",
      danger: true,
    },
  ];
  return (
    <div className={"workbench " + (collapsed ? "is-collapsed" : "")}>
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-icon">
            <BarChartOutlined />
          </span>
          {!collapsed && (
            <span>
              经管之星<small>经营数据工作台</small>
            </span>
          )}
        </div>
        <Button
          className="new-chat"
          aria-label="开启新对话"
          type="primary"
          icon={<PlusOutlined />}
          disabled={busy}
          onClick={() => {
            setPage("ask");
            setCid(null);
            setMsgs([]);
            setError("");
            setInput("");
          }}
        >
          {!collapsed && "开启新对话"}
        </Button>
        <nav>
          <button
            className="nav-item mobile-history"
            aria-label="历史会话"
            onClick={() => setDrawer("history")}
          >
            <HistoryOutlined />
          </button>
          <button className={"nav-item " + (page === "ask" ? "active" : "")} onClick={() => { setPage("ask"); setDrawer(""); }}>
            <MessageOutlined />
            {!collapsed && "智能问数"}
          </button>
          <button className={"nav-item " + (page === "settings" ? "active" : "")} onClick={() => setPage("settings")}>
            <ControlOutlined />
            {!collapsed && "应用配置"}
          </button>
          <button className={"nav-item " + (page === "feedback" ? "active" : "")} onClick={() => setPage("feedback")}>
            <ExclamationCircleOutlined />
            {!collapsed && "回复校对"}
          </button>
        </nav>
        {!collapsed && (
          <div className="history">
            <div className="history-heading">
              最近会话<span>{conversations.length}</span>
            </div>
            <Input
              className="history-search"
              prefix={<SearchOutlined />}
              placeholder="搜索会话"
              variant="borderless"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              allowClear
            />
            <div className="history-list">
              {conversations
                .filter((c) => c.title.includes(search))
                .map((c) => (
                  <div
                    key={c.id}
                    className={
                      "history-item " + (cid === c.id ? "selected" : "")
                    }
                  >
                    <button
                      disabled={busy}
                      onClick={() => loadConversation(c.id)}
                      title={c.title}
                    >
                      {c.pinned && <span className="pin-dot" />}
                      {c.title}
                    </button>
                    <Dropdown
                      menu={{
                        items: actions(c),
                        onClick: (info) => handleConversationAction(c, info.key),
                      }}
                      trigger={["click"]}
                      disabled={busy}
                    >
                      <Button
                        size="small"
                        type="text"
                        icon={<MoreOutlined />}
                        aria-label={"管理会话 " + c.title}
                        onClick={(event) => event.stopPropagation()}
                      />
                    </Dropdown>
                  </div>
                ))}
              {!conversations.length && (
                <p className="history-empty">你的分析记录会保存在这里</p>
              )}
            </div>
          </div>
        )}
        <div className="sidebar-bottom">
          <div className="user-row">
            <span className="avatar">管</span>
            {!collapsed && (
              <>
                <div>
                  {user.display_name}
                  <small>本地工作空间</small>
                </div>
                <Tooltip title="退出登录">
                  <Button
                    type="text"
                    icon={<LogoutOutlined />}
                    disabled={busy}
                    onClick={onLogout}
                  />
                </Tooltip>
              </>
            )}
          </div>
        </div>
      </aside>
      <main className={"main page-" + page}>
        <header className="topbar">
          <div>
            <Button
              type="text"
              icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
              onClick={() => setCollapsed(!collapsed)}
              aria-label="切换侧栏"
            />
            <span className="breadcrumb">
              {page === "ask" ? "工作空间" : page === "settings" ? "系统管理" : "反馈管理"} <span>/</span>{" "}
              <b>{page === "ask" ? "智能问数" : page === "settings" ? "应用配置" : "回复校对"}</b>
            </span>
          </div>
          <div className="topbar-right">
            <Tag color="blue" bordered={false}>
              经营数据
            </Tag>
            <span className="dataset-date">
              更新至 {catalog?.dataset?.cutoff_date || "—"}
            </span>
          </div>
        </header>
        {page === "settings" && <div className="management-page settings-page">
          <div className="page-path">系统管理 <span>/</span> <b>应用配置</b></div>
          <section className="management-card">
            <div className="management-heading"><ControlOutlined /><strong>应用配置</strong><span>以下设置仅对当前用户生效</span></div>
            <WorkbenchSettingsPanel
              settings={workbenchSettings}
              models={catalog?.model.available || []}
              modelConfigured={Boolean(catalog?.model.configured)}
              testing={testing}
              onSave={saveWorkbenchSettings}
              onTest={async (model) => {
                setTesting(true);
                try {
                  const result = await post("/model/test", { model });
                  message.success(`${result.model} 连接成功，耗时 ${(result.duration_ms / 1000).toFixed(1)} 秒`);
                } catch (error) { message.error((error as Error).message); }
                finally { setTesting(false); }
              }}
            />
          </section>
        </div>}
        {page === "feedback" && <FeedbackManagement />}
        <div className="conversation-top">
          <div>
            <MessageOutlined />
            <span>
              {conversations.find((c) => c.id === cid)?.title || "AI 智能问数"}
            </span>
          </div>
          <Tooltip title="查看模型连接状态">
            <Button
              size="small"
              type="text"
              onClick={() => setPage("settings")}
            >
              <span
                className={
                  "model-dot " + (catalog?.model.configured ? "ready" : "")
                }
              />
              {workbenchSettings.llm_model}
            </Button>
          </Tooltip>
        </div>
        {error && (
          <div className="page-error">
            <Alert
              type="error"
              message={error}
              closable
              onClose={() => setError("")}
              showIcon
            />
          </div>
        )}
        <div className="chat-scroll">
          {loadingChat ? (
            <div className="chat-loading">
              <Spin />
            </div>
          ) : !msgs.length ? (
            <div
              className={
                "welcome " +
                (workbenchSettings.welcome_enabled ? "" : "welcome-disabled")
              }
            >
              {workbenchSettings.welcome_enabled && (
                <>
                  <div className="welcome-mark">
                    <BarChartOutlined />
                  </div>
                  <span className="eyebrow">你的经营分析伙伴</span>
                  <h1>{workbenchSettings.welcome_title}</h1>
                  <p>{workbenchSettings.welcome_message}</p>
                  <div className="capability-tags">
                    <span>
                      <CheckCircleOutlined /> 真实 SQL 取数
                    </span>
                    <span>
                      <LineChartOutlined /> 图表自动呈现
                    </span>
                    <span>
                      <MessageOutlined /> 支持连续追问
                    </span>
                  </div>
                  {visibleStarterQuestions.length > 0 && (
                    <>
                      <div className="suggestion-heading">
                        <span>从一个问题开始</span>
                        <button
                          className="suggestion-refresh"
                          disabled={questionPool.length <= 6}
                          onClick={() =>
                            setQuestionOffset(
                              (current) => (current + 6) % questionPool.length,
                            )
                          }
                        >
                          <ReloadOutlined /> 换一批
                        </button>
                      </div>
                      <div className="question-grid">
                        {visibleStarterQuestions.map(
                          (q: string, i: number) => (
                            <button
                              key={q}
                              disabled={busy || !catalog}
                              onClick={() => ask(q)}
                            >
                              <span className={"question-icon qi-" + (i % 6)}>
                                {
                                  [
                                    <BarChartOutlined />,
                                    <PieChartOutlined />,
                                    <LineChartOutlined />,
                                    <ApartmentOutlined />,
                                    <CheckCircleOutlined />,
                                    <DatabaseOutlined />,
                                  ][i % 6]
                                }
                              </span>
                              <span>{q}</span>
                              <ArrowRightOutlined />
                            </button>
                          ),
                        )}
                      </div>
                    </>
                  )}
                </>
              )}
              <div className="data-context">
                <DatabaseOutlined />
                <span>
                  企业软件与服务 ·{" "}
                  {catalog?.dataset?.counts?.contracts?.toLocaleString() || "—"}{" "}
                  份合同 · 10 个经营单元
                </span>
                <button onClick={() => setDrawer("catalog")}>
                  查看数据范围
                </button>
              </div>
            </div>
          ) : (
            <div className="message-list">
              {msgs.map((m) =>
                m.role === "user" ? (
                  <div key={m.id} className="user-message">
                    <div>{m.content}</div>
                    <Tooltip
                      title={
                        favorites.some((item) => item.question === m.content)
                          ? "取消收藏"
                          : "收藏问题"
                      }
                    >
                      <Button
                        type="text"
                        size="small"
                        className={
                          favorites.some((item) => item.question === m.content)
                            ? "favorite-active"
                            : ""
                        }
                        icon={
                          favorites.some((item) => item.question === m.content)
                            ? <StarFilled />
                            : <StarOutlined />
                        }
                        onClick={() => favorite(m.content)}
                      />
                    </Tooltip>
                  </div>
                ) : (
                  <Answer
                    key={m.id}
                    msg={m}
                    onAsk={(q) => ask(q)}
                    onFeedback={setFeedback}
                  />
                ),
              )}
              {busy && (
                <div className="assistant-row processing">
                  <div className="assistant-icon">
                    <BarChartOutlined />
                  </div>
                  <div className="thinking-state">
                    <div className="thinking-title">
                      <Spin size="small" />
                      <strong>正在思考</strong>
                      <span className="thinking-dots" aria-hidden="true">
                        <i />
                        <i />
                        <i />
                      </span>
                    </div>
                    <p key={`${stage}-${thinkingIndex}`}>
                      {(THINKING_COPY[stage] || ["正在理解你的问题并准备查询"])[
                        thinkingIndex % (THINKING_COPY[stage]?.length || 1)
                      ]}
                    </p>
                  </div>
                </div>
              )}
              <div ref={end} />
            </div>
          )}
        </div>
        <footer className="composer-wrap">
          <div className={"composer " + (busy ? "processing-input" : "")}>
            <Input.TextArea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              autoSize={{ minRows: 2, maxRows: 6 }}
              maxLength={1000}
              placeholder={
                msgs.length
                  ? "继续追问，例如：只看华东区，按月展开…"
                  : "输入你的经营问题，例如：今年各产品线收入比去年增长了多少？"
              }
              variant="borderless"
              onKeyDown={(e) => {
                if (
                  e.key === "Enter" &&
                  !e.shiftKey &&
                  !e.nativeEvent.isComposing
                ) {
                  e.preventDefault();
                  ask();
                }
              }}
              disabled={loadingChat}
            />
            <div className="composer-bottom">
              <div className="composer-left-actions">
                <QuickQuestions
                  open={quickOpen}
                  onOpenChange={setQuickOpen}
                  common={commonQuestions}
                  favorites={favorites}
                  commonEnabled={workbenchSettings.common_questions_enabled}
                  onRemoveCommon={removeCommonQuestion}
                  onRemoveFavorite={removeFavorite}
                  onPick={(question) => {
                    setInput(question);
                    setQuickOpen(false);
                  }}
                />
                <button onClick={() => setDrawer("catalog")}>
                  <DatabaseOutlined /> 企业经营数据 <span>13 张业务表</span>
                </button>
              </div>
              <div>
                <span className="enter-hint">
                  Enter 发送 · Shift + Enter 换行
                </span>
                <Tooltip title={recording ? "结束录音" : transcribing ? "正在识别" : "语音输入"}>
                  <Button
                    className={recording ? "voice-input recording" : "voice-input"}
                    shape="circle"
                    icon={transcribing ? <LoadingOutlined spin /> : <AudioOutlined />}
                    onClick={toggleRecording}
                    disabled={busy || loadingChat || transcribing}
                    aria-label={recording ? "结束录音" : "开始语音输入"}
                  />
                </Tooltip>
                {busy ? (
                  <Tooltip title="停止生成">
                    <Button
                      shape="circle"
                      icon={<StopOutlined />}
                      onClick={() => abort.current?.abort()}
                      aria-label="停止生成"
                    />
                  </Tooltip>
                ) : (
                  <Button
                    type="primary"
                    shape="circle"
                    icon={<ArrowUpOutlined />}
                    onClick={() => ask()}
                    disabled={!input.trim() || !catalog || loadingChat}
                    aria-label="发送问题"
                  />
                )}
              </div>
            </div>
          </div>
          <p className="composer-note">
            相对时间以数据截止日为准，重要决策请核对指标口径。
          </p>
        </footer>
      </main>
      <Drawer
        title={
          drawer === "history"
            ? "历史会话"
            : drawer === "catalog"
              ? "数据与指标"
              : drawer === "favorites"
                ? "收藏问题"
                : "工作台设置"
        }
        open={!!drawer}
        onClose={() => setDrawer("")}
        width={600}
      >
        {drawer === "history" && (
          <div className="favorite-list">
            {conversations.length ? (
              conversations.map((c) => (
                <div key={c.id}>
                  <button
                    disabled={busy}
                    onClick={() => {
                      setDrawer("");
                      loadConversation(c.id);
                    }}
                  >
                    {c.title}
                    <ArrowRightOutlined />
                  </button>
                </div>
              ))
            ) : (
              <Empty description="暂无会话记录" />
            )}
          </div>
        )}
        {drawer === "catalog" && catalog && (
          <>
            <Alert
              type="info"
              message="算力基础设施与服务 · 经营数据"
              description={`覆盖 ${catalog.dataset.start_date} 至 ${catalog.dataset.cutoff_date}，固定种子生成，所有金额采用不含税管理口径。`}
              showIcon
            />
            <Tabs
              items={[
                {
                  key: "metrics",
                  label: "指标口径",
                  children: (
                    <div className="metric-list">
                      {Object.entries(catalog.metrics).map(
                        ([key, m]: [string, any]) => (
                          <div key={key}>
                            <h3>
                              {m.name}
                              <Tag>{m.unit}</Tag>
                            </h3>
                            <p>{m.definition}</p>
                            <small>{key} · v1</small>
                          </div>
                        ),
                      )}
                    </div>
                  ),
                },
                {
                  key: "data",
                  label: "数据范围",
                  children: (
                    <>
                      <h3>经营单元</h3>
                      <div className="tag-wrap">
                        {catalog.values.org_unit.map((v: string) => (
                          <Tag key={v}>{v}</Tag>
                        ))}
                      </div>
                      <h3>产品线</h3>
                      <div className="tag-wrap">
                        {catalog.values.product_line.map((v: string) => (
                          <Tag key={v}>{v}</Tag>
                        ))}
                      </div>
                      <h3>数据记录</h3>
                      <Table
                        rowKey="table"
                        size="small"
                        pagination={false}
                        columns={[
                          { title: "数据表", dataIndex: "table" },
                          {
                            title: "数据表描述",
                            dataIndex: "description",
                          },
                          {
                            title: "记录数",
                            dataIndex: "count",
                            align: "right",
                          },
                        ]}
                        dataSource={catalog.data_tables || []}
                        scroll={{ x: 620 }}
                      />
                    </>
                  ),
                },
              ]}
            />
          </>
        )}
        {drawer === "favorites" &&
          (favorites.length ? (
            <div className="favorite-list">
              {favorites.map((f) => (
                <div key={f.id}>
                  <button
                    disabled={busy}
                    onClick={() => {
                      setDrawer("");
                      ask(f.question);
                    }}
                  >
                    {f.question}
                    <ArrowRightOutlined />
                  </button>
                  <Popconfirm
                    title="取消收藏这个问题？"
                    onConfirm={async () => {
                      await removeFavorite(f.id);
                    }}
                  >
                    <Button type="text" size="small">
                      取消收藏
                    </Button>
                  </Popconfirm>
                </div>
              ))}
            </div>
          ) : (
            <Empty description="点击问题旁的星标，即可收藏" />
          ))}
      </Drawer>
      <Modal
        title="回答反馈"
        open={!!feedback}
        onCancel={() => {
          setFeedback("");
          setRemark("");
        }}
        okText="提交反馈"
        cancelText="取消"
        okButtonProps={{ disabled: !remark.trim() }}
        onOk={async () => {
          try {
            await post("/feedbacks", { message_id: feedback, comment: remark });
            message.success("反馈已保存");
            setFeedback("");
            setRemark("");
          } catch (e) {
            message.error((e as Error).message);
          }
        }}
      >
        <p>请说明有疑问的数据或口径，帮助后续核查。</p>
        <Input.TextArea
          value={remark}
          onChange={(e) => setRemark(e.target.value)}
          maxLength={1000}
          rows={4}
          placeholder="例如：收入统计范围与预期不一致…"
        />
      </Modal>
      <Modal
        title="重命名会话"
        open={!!rename}
        onCancel={() => setRename(null)}
        okText="保存"
        cancelText="取消"
        okButtonProps={{ disabled: !renameText.trim() }}
        onOk={async () => {
          try {
            await api("/conversations/" + rename.id, {
              method: "PATCH",
              body: JSON.stringify({ title: renameText.trim() }),
            });
            setRename(null);
            await refresh();
          } catch (e) {
            message.error((e as Error).message);
          }
        }}
      >
        <Input
          value={renameText}
          onChange={(e) => setRenameText(e.target.value)}
          maxLength={100}
        />
      </Modal>
    </div>
  );
}
