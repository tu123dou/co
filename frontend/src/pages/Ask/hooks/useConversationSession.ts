import { useCallback, useEffect, useReducer, useRef } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { createConversation, fetchConversation, streamQuestion } from "../../../api/conversations";
import { initialSessionState, sessionReducer } from "../model/sessionReducer";
import type { ChatMessage } from "../../../api/conversations";

function temporaryId(prefix: string) {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export function useConversationSession(
  onConversationChanged: () => Promise<void>,
  onQuestionCompleted: () => Promise<void>,
) {
  const [state, dispatch] = useReducer(sessionReducer, initialSessionState);
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const loadController = useRef<AbortController | null>(null);
  const streamController = useRef<AbortController | null>(null);
  const loadVersion = useRef(0);
  const generationVersion = useRef(0);
  const sending = useRef(false);
  const internallyCreated = useRef<string | null>(null);

  useEffect(() => {
    const id = searchParams.get("conversation");
    loadController.current?.abort();
    loadVersion.current += 1;
    const version = loadVersion.current;

    if (internallyCreated.current === id) {
      internallyCreated.current = null;
      return;
    }

    if (sending.current) {
      generationVersion.current += 1;
      streamController.current?.abort();
      sending.current = false;
    }

    if (!id) {
      dispatch({ type: "conversation/reset" });
      return;
    }

    const controller = new AbortController();
    loadController.current = controller;
    dispatch({ type: "conversation/loading", id });
    fetchConversation(id, controller.signal)
      .then((conversation) => {
        if (version === loadVersion.current) {
          dispatch({ type: "conversation/loaded", id, messages: conversation.messages });
        }
      })
      .catch((cause) => {
        if ((cause as Error).name !== "AbortError" && version === loadVersion.current) {
          dispatch({ type: "conversation/failed", message: (cause as Error).message });
        }
      });
    return () => controller.abort();
  }, [searchParams.toString()]);

  useEffect(
    () => () => {
      loadController.current?.abort();
      streamController.current?.abort();
    },
    [],
  );

  const ask = useCallback(
    async (question = state.draft) => {
      const cleanQuestion = question.trim();
      if (!cleanQuestion || sending.current) return;

      sending.current = true;
      const version = ++generationVersion.current;
      const existingId = state.conversationId;
      dispatch({ type: "generation/creating" });
      const controller = new AbortController();
      streamController.current = controller;
      let conversationId = existingId;
      let receivedResult = false;

      try {
        if (!conversationId) {
          conversationId = (await createConversation()).id;
          if (version !== generationVersion.current) return;
          internallyCreated.current = conversationId;
          navigate(`/ask?conversation=${encodeURIComponent(conversationId)}`, { replace: true });
          await onConversationChanged();
        }

        const userMessage: ChatMessage = {
          id: temporaryId("user"),
          role: "user",
          content: cleanQuestion,
        };
        dispatch({ type: "generation/started", id: conversationId, question: userMessage });

        await streamQuestion(conversationId, cleanQuestion, controller.signal, (event) => {
          if (version !== generationVersion.current) return;
          if (event.type === "status") dispatch({ type: "generation/stage", stage: event.stage });
          if (event.type === "analysis")
            dispatch({ type: "generation/analysis", step: event.step });
          if (event.type === "result") {
            receivedResult = true;
            dispatch({ type: "generation/result", message: event.message });
          }
        });
        if (!receivedResult) throw new Error("连接提前结束，未收到完整回答");
      } catch (cause) {
        if (version !== generationVersion.current) return;
        if ((cause as Error).name === "AbortError") {
          dispatch({
            type: "generation/cancelled",
            message: {
              id: temporaryId("cancelled"),
              role: "assistant",
              content: "本次生成已停止。",
              result: { status: "cancelled" },
            },
          });
        } else {
          dispatch({
            type: "generation/failed",
            message: (cause as Error).message,
            draft: cleanQuestion,
          });
        }
      } finally {
        if (version === generationVersion.current) {
          sending.current = false;
          streamController.current = null;
          await Promise.allSettled([onConversationChanged(), onQuestionCompleted()]);
        }
      }
    },
    [navigate, onConversationChanged, onQuestionCompleted, state.conversationId, state.draft],
  );

  const stop = useCallback(() => {
    if (!sending.current) return;
    dispatch({ type: "generation/cancelling" });
    streamController.current?.abort();
  }, []);

  const retry = useCallback(() => {
    const lastQuestion = [...state.messages].reverse().find((item) => item.role === "user");
    if (lastQuestion) void ask(lastQuestion.content);
  }, [ask, state.messages]);

  return {
    ...state,
    busy: state.generation !== "idle",
    setDraft: (value: string) => dispatch({ type: "draft/changed", value }),
    dismissError: () => dispatch({ type: "error/dismissed" }),
    ask,
    retry,
    stop,
  };
}
