import { Button, Input, Tooltip } from "antd";
import type { RefObject } from "react";
import type { TextAreaRef } from "antd/es/input/TextArea";
import {
  ArrowUpOutlined,
  AudioOutlined,
  DatabaseOutlined,
  LoadingOutlined,
  StopOutlined,
} from "@ant-design/icons";
import type { AskSettings, Catalog } from "../../../api/workbench";
import type { CommonQuestion, FavoriteQuestion } from "../../../api/questions";
import styles from "../AskPage.module.scss";
import QuickQuestionPanel from "./QuickQuestionPanel";

export default function AskComposer({
  inputRef,
  draft,
  hasMessages,
  busy,
  loadingConversation,
  catalog,
  settings,
  commonQuestions,
  favorites,
  quickOpen,
  recording,
  transcribing,
  onDraft,
  onAsk,
  onStop,
  onToggleRecording,
  onQuickOpen,
  onCatalog,
  onRemoveCommon,
  onRemoveFavorite,
}: {
  inputRef: RefObject<TextAreaRef | null>;
  draft: string;
  hasMessages: boolean;
  busy: boolean;
  loadingConversation: boolean;
  catalog: Catalog | null;
  settings: AskSettings;
  commonQuestions: CommonQuestion[];
  favorites: FavoriteQuestion[];
  quickOpen: boolean;
  recording: boolean;
  transcribing: boolean;
  onDraft: (value: string) => void;
  onAsk: () => void;
  onStop: () => void;
  onToggleRecording: () => void;
  onQuickOpen: (open: boolean) => void;
  onCatalog: () => void;
  onRemoveCommon: (id: number) => Promise<void>;
  onRemoveFavorite: (id: number) => Promise<void>;
}) {
  return (
    <footer className={styles["ask-composer-wrap"]}>
      <div className={styles["ask-composer"]}>
        <Input.TextArea
          ref={inputRef}
          value={draft}
          onChange={(event) => onDraft(event.target.value)}
          autoSize={{ minRows: 2, maxRows: 6 }}
          maxLength={1000}
          variant="borderless"
          disabled={loadingConversation}
          placeholder={
            hasMessages
              ? "继续追问，例如：只看华东区，按月展开…"
              : "输入你的经营问题，例如：今年各产品线收入比去年增长了多少？"
          }
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
              event.preventDefault();
              onAsk();
            }
          }}
        />
        <div className={styles["ask-composer__toolbar"]}>
          <div className={styles["ask-composer__sources"]}>
            <QuickQuestionPanel
              open={quickOpen}
              onOpenChange={onQuickOpen}
              common={commonQuestions}
              favorites={favorites}
              commonEnabled={settings.common_questions_enabled}
              onChoose={(question) => {
                onDraft(question);
                onQuickOpen(false);
              }}
              onRemoveCommon={onRemoveCommon}
              onRemoveFavorite={onRemoveFavorite}
            />
            <button onClick={onCatalog}>
              <DatabaseOutlined /> 企业经营数据{" "}
              <span>{catalog?.data_tables.length ?? "—"} 张业务表</span>
            </button>
          </div>
          <div className={styles["ask-composer__send"]}>
            <span>Enter 发送 · Shift + Enter 换行</span>
            <Tooltip title={recording ? "结束录音" : transcribing ? "正在识别" : "语音输入"}>
              <Button
                className={recording ? styles["is-recording"] : undefined}
                shape="circle"
                icon={transcribing ? <LoadingOutlined spin /> : <AudioOutlined />}
                onClick={onToggleRecording}
                disabled={busy || loadingConversation || transcribing}
                aria-label={recording ? "结束录音" : "开始语音输入"}
              />
            </Tooltip>
            {busy ? (
              <Tooltip title="停止生成">
                <Button
                  shape="circle"
                  icon={<StopOutlined />}
                  onClick={onStop}
                  aria-label="停止生成"
                />
              </Tooltip>
            ) : (
              <Button
                type="primary"
                shape="circle"
                icon={<ArrowUpOutlined />}
                onClick={onAsk}
                disabled={!draft.trim() || !catalog || loadingConversation}
                aria-label="发送问题"
              />
            )}
          </div>
        </div>
      </div>
      <p>相对时间以数据截止日为准，重要决策请核对指标口径。</p>
    </footer>
  );
}
