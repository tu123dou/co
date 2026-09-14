import { Button, Spin, Tooltip } from "antd";
import type { RefObject } from "react";
import { BarChartOutlined, StarFilled, StarOutlined } from "@ant-design/icons";
import type { AnalysisStep } from "../../../models/ask";
import type { ChatMessage } from "../../../api/conversations";
import type { FavoriteQuestion } from "../../../api/questions";
import styles from "../AskPage.module.scss";
import AnalysisDetails from "./AnalysisDetails";
import AssistantMessage from "./AssistantMessage";

export default function MessageTimeline({
  messages,
  favorites,
  busy,
  stage,
  liveAnalysis,
  endRef,
  onFavorite,
  onAsk,
  onRetry,
  onFeedback,
}: {
  messages: ChatMessage[];
  favorites: FavoriteQuestion[];
  busy: boolean;
  stage: string;
  liveAnalysis: AnalysisStep[];
  endRef: RefObject<HTMLDivElement | null>;
  onFavorite: (question: string) => void;
  onAsk: (question: string) => void;
  onRetry: () => void;
  onFeedback: (messageId: string) => void;
}) {
  return (
    <div className={styles["ask-timeline"]}>
      {messages.map((item) =>
        item.role === "user" ? (
          <div className={styles["ask-user-message"]} key={item.id}>
            <div>{item.content}</div>
            <Tooltip
              title={
                favorites.some((favorite) => favorite.question === item.content)
                  ? "取消收藏"
                  : "收藏问题"
              }
            >
              <Button
                type="text"
                size="small"
                className={
                  favorites.some((favorite) => favorite.question === item.content)
                    ? styles["is-favorite"]
                    : undefined
                }
                icon={
                  favorites.some((favorite) => favorite.question === item.content) ? (
                    <StarFilled />
                  ) : (
                    <StarOutlined />
                  )
                }
                onClick={() => onFavorite(item.content)}
              />
            </Tooltip>
          </div>
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
      {busy && (
        <div className={styles["ask-progress"]}>
          <div className={styles["ask-answer__avatar"]}>
            <BarChartOutlined />
          </div>
          <div className={styles["ask-progress__body"]}>
            <div className={styles["ask-progress__title"]}>
              <Spin size="small" />
              <strong>{stage || "正在准备"}</strong>
              <span>
                <i />
                <i />
                <i />
              </span>
            </div>
            <AnalysisDetails steps={liveAnalysis} live />
          </div>
        </div>
      )}
      <div ref={endRef} />
    </div>
  );
}
