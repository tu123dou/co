import { Spin } from "antd";
import { useEffect, useState, type RefObject } from "react";
import { BarChartOutlined } from "@ant-design/icons";
import type { ChatMessage } from "../../../api/conversations";
import type { FavoriteQuestion } from "../../../api/questions";
import styles from "../AskPage.module.scss";
import AssistantMessage from "./AssistantMessage";
import UserMessage from "./UserMessage";

// 由真实阶段选择提示组；组内轮播不表示对应操作已完成。
const STAGE_HINTS = new Map<string, readonly string[]>([
  ["理解问题", ["正在识别指标、时间范围和筛选条件", "正在匹配业务口径与相关数据表"]],
  ["执行取数", ["正在组织查询逻辑并校验取数范围", "正在查询数据，请稍候"]],
  ["整理结果", ["正在核对查询结果与关键数值", "正在整理分析结论和展示内容"]],
]);
const FALLBACK_HINTS = ["正在理解你的问题并准备查询"];

function ThinkingIndicator({ stage }: { stage: string }) {
  const [hintIndex, setHintIndex] = useState(0);
  const hints = STAGE_HINTS.get(stage) ?? FALLBACK_HINTS;

  useEffect(() => {
    if (hints.length < 2) return;
    const timer = window.setInterval(() => {
      setHintIndex((index) => (index + 1) % hints.length);
    }, 2400);
    return () => window.clearInterval(timer);
  }, [hints]);

  return (
    <div className={styles["ask-progress"]} role="status" aria-label="正在思考">
      <div className={styles["ask-answer__avatar"]} aria-hidden="true">
        <BarChartOutlined />
      </div>
      <div className={styles["ask-progress__body"]}>
        <div className={styles["ask-progress__title"]}>
          <Spin size="small" />
          <strong>正在思考</strong>
          <span aria-hidden="true">
            <i />
            <i />
            <i />
          </span>
        </div>
        <p key={hintIndex} className={styles["ask-progress__hint"]} aria-hidden="true">
          {hints[hintIndex]}
        </p>
      </div>
    </div>
  );
}

export default function MessageTimeline({
  messages,
  favorites,
  busy,
  stage,
  endRef,
  onFavorite,
  onAsk,
  onEdit,
  onRetry,
  onFeedback,
}: {
  messages: ChatMessage[];
  favorites: FavoriteQuestion[];
  busy: boolean;
  stage: string;
  endRef: RefObject<HTMLDivElement | null>;
  onFavorite: (question: string) => void;
  onAsk: (question: string) => void;
  onEdit: (question: string) => void;
  onRetry: () => void;
  onFeedback: (messageId: string) => void;
}) {
  return (
    <div className={styles["ask-timeline"]}>
      {messages.map((item) =>
        item.role === "user" ? (
          <UserMessage
            key={item.id}
            question={item.content}
            favorite={favorites.some((favorite) => favorite.question === item.content)}
            busy={busy}
            onFavorite={onFavorite}
            onEdit={onEdit}
            onAsk={onAsk}
          />
        ) : (
          <AssistantMessage
            key={item.id}
            message={item}
            onAsk={onAsk}
            onRetry={onRetry}
            onFeedback={onFeedback}
          />
        ),
      )}
      {busy && <ThinkingIndicator key={stage} stage={stage} />}
      <div ref={endRef} />
    </div>
  );
}
