import { Alert, Button, Tooltip, message as toast } from "antd";
import {
  ArrowRightOutlined,
  BarChartOutlined,
  CheckCircleOutlined,
  CopyOutlined,
  FlagOutlined,
  LoadingOutlined,
  PauseCircleOutlined,
  ReloadOutlined,
  SoundOutlined,
} from "@ant-design/icons";
import { useSpeechPlayer } from "../hooks/useSpeechPlayer";
import type { ChatMessage } from "../../../api/conversations";
import styles from "../AskPage.module.scss";
import AnalysisDetails from "./AnalysisDetails";
import ResultPanel from "./ResultPanel";

export default function AssistantMessage({
  message,
  onAsk,
  onRetry,
  onFeedback,
}: {
  message: ChatMessage;
  onAsk: (question: string) => void;
  onRetry: () => void;
  onFeedback: (messageId: string) => void;
}) {
  const speech = useSpeechPlayer(message.content);
  const result = message.result?.status === "success" ? message.result : null;

  if (!result) {
    const failed = message.result?.status === "error";
    return (
      <article className={styles["ask-answer"]}>
        <div className={styles["ask-answer__avatar"]}>
          <BarChartOutlined />
        </div>
        <div className={styles["ask-answer__body"]}>
          <div className={styles["ask-answer__byline"]}>
            <strong>经管之星</strong>
            <span>AI 问数助手</span>
          </div>
          <Alert type={failed ? "error" : "info"} message={message.content} showIcon />
          {failed ? (
            <Button size="small" icon={<ReloadOutlined />} onClick={onRetry}>
              重新尝试
            </Button>
          ) : (
            <Button
              size="small"
              icon={
                speech.loading ? (
                  <LoadingOutlined spin />
                ) : speech.playing ? (
                  <PauseCircleOutlined />
                ) : (
                  <SoundOutlined />
                )
              }
              disabled={speech.loading}
              onClick={speech.toggle}
            >
              {speech.playing ? "暂停播放" : "播放回答"}
            </Button>
          )}
        </div>
      </article>
    );
  }

  const responseTime = result.completed_at ?? message.created_at;
  return (
    <article className={styles["ask-answer"]}>
      <div className={styles["ask-answer__avatar"]}>
        <BarChartOutlined />
      </div>
      <div className={styles["ask-answer__body"]}>
        <div className={styles["ask-answer__byline"]}>
          <strong>经管之星</strong>
          <span>AI 问数助手</span>
          <span className={styles["ask-answer__verified"]}>
            <CheckCircleOutlined /> 已核对取数
          </span>
        </div>
        <AnalysisDetails steps={result.analysis_process ?? []} />
        <p className={styles["ask-answer__text"]}>{message.content}</p>
        <ResultPanel messageId={message.id} result={result} />
        <div className={styles["ask-answer__actions"]}>
          <div>
            <Tooltip title="复制结论">
              <Button
                type="text"
                icon={<CopyOutlined />}
                aria-label="复制结论"
                onClick={async () => {
                  try {
                    await navigator.clipboard.writeText(message.content);
                    toast.success("已复制");
                  } catch {
                    toast.error("复制失败，请手动选择文本");
                  }
                }}
              />
            </Tooltip>
            <Tooltip title="反馈问题">
              <Button
                type="text"
                icon={<FlagOutlined />}
                aria-label="反馈问题"
                onClick={() => onFeedback(message.id)}
              />
            </Tooltip>
            <Tooltip title={speech.playing ? "暂停播放" : "播放回答"}>
              <Button
                type="text"
                disabled={speech.loading}
                onClick={speech.toggle}
                aria-label={speech.playing ? "暂停播放" : "播放回答"}
                icon={
                  speech.loading ? (
                    <LoadingOutlined spin />
                  ) : speech.playing ? (
                    <PauseCircleOutlined />
                  ) : (
                    <SoundOutlined />
                  )
                }
              />
            </Tooltip>
          </div>
          <span>
            耗时 {(result.duration_ms / 1000).toFixed(1)}s
            {result.usage?.total_tokens !== undefined && ` · Token ${result.usage.total_tokens}`}
            {responseTime &&
              ` · ${new Date(responseTime).toLocaleTimeString("zh-CN", { hour12: false })}`}
          </span>
        </div>
        {!!result.suggestions?.length && (
          <div className={styles["ask-followups"]}>
            {result.suggestions.map((question) => (
              <button key={question} onClick={() => onAsk(question)}>
                {question}
                <ArrowRightOutlined />
              </button>
            ))}
          </div>
        )}
      </div>
    </article>
  );
}
