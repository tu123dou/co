import { Button, Tooltip, message } from "antd";
import {
  CopyOutlined,
  EditOutlined,
  ReloadOutlined,
  StarFilled,
  StarOutlined,
} from "@ant-design/icons";
import { useRef } from "react";
import styles from "../AskPage.module.scss";

export default function UserMessage({
  question,
  favorite,
  busy,
  onFavorite,
  onEdit,
  onAsk,
}: {
  question: string;
  favorite: boolean;
  busy: boolean;
  onFavorite: (question: string) => void;
  onEdit: (question: string) => void;
  onAsk: (question: string) => void;
}) {
  const copyRef = useRef<HTMLTextAreaElement>(null);

  async function copyQuestion() {
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(question);
      } else {
        // 公网 HTTP 部署没有 Clipboard API，保留用户点击触发的复制兼容路径。
        const textarea = copyRef.current;
        if (!textarea) throw new Error("复制不可用");
        const activeElement = document.activeElement;
        try {
          textarea.select();
          if (!document.execCommand("copy")) throw new Error("复制失败");
        } finally {
          if (activeElement instanceof HTMLElement) activeElement.focus();
        }
      }
      message.success("已复制问题");
    } catch {
      message.error("复制失败，请手动选择文本");
    }
  }

  return (
    <div className={styles["ask-user-message"]}>
      <div className={styles["ask-user-message__bubble"]}>{question}</div>
      <div className={styles["ask-user-message__actions"]} role="group" aria-label="问题操作">
        <Tooltip title={favorite ? "取消收藏" : "收藏问题"}>
          <Button
            type="text"
            size="small"
            aria-label={favorite ? "取消收藏" : "收藏问题"}
            aria-pressed={favorite}
            className={favorite ? styles["is-favorite"] : undefined}
            icon={favorite ? <StarFilled /> : <StarOutlined />}
            onClick={() => onFavorite(question)}
          />
        </Tooltip>
        <Tooltip title="编辑问题">
          <Button
            type="text"
            size="small"
            aria-label="编辑问题"
            icon={<EditOutlined />}
            disabled={busy}
            onClick={() => onEdit(question)}
          />
        </Tooltip>
        <Tooltip title="重新提问">
          <Button
            type="text"
            size="small"
            aria-label="重新提问"
            icon={<ReloadOutlined />}
            disabled={busy}
            onClick={() => onAsk(question)}
          />
        </Tooltip>
        <Tooltip title="复制问题">
          <Button
            type="text"
            size="small"
            aria-label="复制问题"
            icon={<CopyOutlined />}
            onClick={() => void copyQuestion()}
          />
        </Tooltip>
      </div>
      <textarea
        ref={copyRef}
        className={styles["ask-user-message__copy"]}
        value={question}
        readOnly
        tabIndex={-1}
        aria-hidden="true"
      />
    </div>
  );
}
