import { useCallback, useEffect, useMemo, useState } from "react";
import { message } from "antd";
import {
  addFavorite,
  deleteCommonQuestion,
  deleteFavorite,
  listCommonQuestions,
  listFavorites,
} from "../../../api/questions";
import { getCatalog, getWorkbenchSettings } from "../../../api/workbench";
import type { AskSettings, Catalog } from "../../../api/workbench";
import type { CommonQuestion, FavoriteQuestion } from "../../../api/questions";

const FALLBACK_SETTINGS: AskSettings = {
  welcome_enabled: true,
  welcome_title: "你好，今天想了解哪些数据？",
  welcome_message: "从收入趋势到目标达成，用自然语言探索你的经营数据。",
  starter_questions: [],
  suggestions_enabled: true,
  common_questions_enabled: true,
  common_question_threshold: 3,
  llm_model: "qwen3.8-max",
};

export function useAskResources() {
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [settings, setSettings] = useState<AskSettings>(FALLBACK_SETTINGS);
  const [commonQuestions, setCommonQuestions] = useState<CommonQuestion[]>([]);
  const [favorites, setFavorites] = useState<FavoriteQuestion[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const refreshCommon = useCallback(
    async () => setCommonQuestions(await listCommonQuestions()),
    [],
  );
  const refreshFavorites = useCallback(async () => setFavorites(await listFavorites()), []);

  useEffect(() => {
    let active = true;
    Promise.all([getCatalog(), getWorkbenchSettings(), listCommonQuestions(), listFavorites()])
      .then(([nextCatalog, nextSettings, nextCommon, nextFavorites]) => {
        if (!active) return;
        setCatalog(nextCatalog);
        setSettings(nextSettings);
        setCommonQuestions(nextCommon);
        setFavorites(nextFavorites);
      })
      .catch((cause) => active && setError((cause as Error).message))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, []);

  const questions = useMemo(
    () => Array.from(new Set([...settings.starter_questions, ...(catalog?.examples ?? [])])),
    [catalog?.examples, settings.starter_questions],
  );

  const toggleFavorite = useCallback(
    async (question: string) => {
      const saved = favorites.find((item) => item.question === question);
      try {
        if (saved) await deleteFavorite(saved.id);
        else await addFavorite(question);
        await refreshFavorites();
        message.success(saved ? "已取消收藏" : "已收藏问题");
      } catch (cause) {
        message.error((cause as Error).message);
      }
    },
    [favorites, refreshFavorites],
  );

  const removeFavorite = useCallback(
    async (id: number) => {
      await deleteFavorite(id);
      await refreshFavorites();
      message.success("已取消收藏");
    },
    [refreshFavorites],
  );

  const removeCommonQuestion = useCallback(
    async (id: number) => {
      await deleteCommonQuestion(id);
      await refreshCommon();
      message.success("已删除常见问题");
    },
    [refreshCommon],
  );

  return {
    catalog,
    settings,
    commonQuestions,
    favorites,
    questions,
    loading,
    error,
    dismissError: () => setError(""),
    refreshCommon,
    toggleFavorite,
    removeFavorite,
    removeCommonQuestion,
  };
}
