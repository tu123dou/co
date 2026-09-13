import { useEffect, useRef, useState } from "react";
import { message } from "antd";
import { useNavigate, useOutletContext, useSearchParams } from "react-router-dom";
import { ROUTES } from "../../../router/paths";
import {
  askQuestion, createConversation, getConversation, readAskEvents,
} from "../../../api/conversations";
import {
  getCatalog, getWorkbenchSettings,
} from "../../../api/workbench";
import { addFavorite, deleteCommonQuestion, deleteFavorite, listCommonQuestions, listFavorites } from "../../../api/questions";
import type { Msg } from "../../../models/query";
import type { FavoriteQuestion, WorkbenchCatalog } from "../../../models/workbench";
import type { WorkspaceOutletContext } from "../../../layouts/WorkspaceLayout/WorkspaceLayout";
import {
  DEFAULT_WORKBENCH_SETTINGS,
  type CommonQuestion,
  type WorkbenchSettings,
} from "../../../config/workbench";
import useVoiceInput from "./useVoiceInput";

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

export default function useWorkbenchController() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { conversations, refreshConversations } = useOutletContext<WorkspaceOutletContext>();
  const [catalog, setCatalog] = useState<WorkbenchCatalog | null>(null),
    [workbenchSettings, setWorkbenchSettings] = useState<WorkbenchSettings>(
      DEFAULT_WORKBENCH_SETTINGS,
    ),
    [quickOpen, setQuickOpen] = useState(false),
    [questionOffset, setQuestionOffset] = useState(0),
    [commonQuestions, setCommonQuestions] = useState<CommonQuestion[]>([]),
    [favorites, setFavorites] = useState<FavoriteQuestion[]>([]),
    [cid, setCid] = useState<string | null>(null),
    [msgs, setMsgs] = useState<Msg[]>([]),
    [input, setInput] = useState(""),
    [busy, setBusy] = useState(false),
    [stage, setStage] = useState(""),
    [thinkingIndex, setThinkingIndex] = useState(0),
    [error, setError] = useState(""),
    [loadingChat, setLoadingChat] = useState(false);
  const abort = useRef<AbortController | null>(null),
    end = useRef<HTMLDivElement>(null),
    sending = useRef(false);
  const voice = useVoiceInput((text) => setInput((current) => current.trim() ? `${current.trim()} ${text}` : text));
  const refreshCommonQuestions = () => listCommonQuestions().then(setCommonQuestions);
  useEffect(() => {
    Promise.all([
      getCatalog().then(setCatalog),
      getWorkbenchSettings().then(setWorkbenchSettings),
      refreshCommonQuestions(),
      listFavorites().then(setFavorites),
      refreshConversations(),
    ]).catch((e) => setError(e.message));
  }, []);
  useEffect(() => {
    const conversationId = searchParams.get("conversation");
    if (conversationId) {
      loadConversation(conversationId);
      return;
    }
    if (searchParams.has("new")) {
      setCid(null);
      setMsgs([]);
      setInput("");
      setError("");
    }
  }, [searchParams.toString()]);
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
  async function loadConversation(id: string) {
    if (sending.current) return;
    setLoadingChat(true);
    setError("");
    try {
      const c = await getConversation(id);
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
        const c = await createConversation();
        id = c.id;
        setCid(id);
        navigate(`${ROUTES.ask}?conversation=${encodeURIComponent(id)}`, { replace: true });
        await refreshConversations();
      }
      setMsgs((m) => [
        ...m,
        { id: createClientMessageId(), role: "user", content: question },
      ]);
      const response = await askQuestion(id, question, controller.signal);
      let gotResult = false;
      await readAskEvents(response, (event) => {
        if (event.type === "status") setStage(event.stage);
        if (event.type === "result") {
          gotResult = true;
          setMsgs((messages) => [...messages, event.message]);
        }
      });
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
      refreshConversations().catch(() => {});
      refreshCommonQuestions().catch(() => {});
    }
  }
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
  const retry = () => {
    const previousQuestion = [...msgs].reverse().find((message) => message.role === "user")?.content;
    if (previousQuestion) ask(previousQuestion);
  };
  const favorite = async (question: string) => {
    try {
      const saved = favorites.find((item) => item.question === question);
      if (saved) await deleteFavorite(saved.id);
      else await addFavorite(question);
      setFavorites(await listFavorites());
      message.success(saved ? "已取消收藏" : "已收藏问题");
    } catch (cause) {
      message.error((cause as Error).message);
    }
  };
  const removeFavorite = async (id: number) => {
    await deleteFavorite(id);
    setFavorites(await listFavorites());
    message.success("已取消收藏");
  };
  const removeCommonQuestion = async (id: number) => {
    await deleteCommonQuestion(id);
    setCommonQuestions(await listCommonQuestions());
    message.success("已删除常见问题");
  };
  return {
    catalog, workbenchSettings, commonQuestions, quickOpen, setQuickOpen, questionPool,
    visibleStarterQuestions, setQuestionOffset, conversations, cid, msgs, input, setInput,
    busy, stage, thinkingIndex, thinkingCopy: THINKING_COPY, favorites, error, setError, loadingChat,
    recording: voice.recording, transcribing: voice.transcribing, abort, end, ask, retry,
    favorite, removeFavorite, removeCommonQuestion, toggleRecording: voice.toggleRecording,
  };
}
