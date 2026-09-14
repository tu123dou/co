import { useEffect, useRef, useState } from "react";
import { Alert, Button, Spin, Tooltip } from "antd";
import type { TextAreaRef } from "antd/es/input/TextArea";
import { MessageOutlined } from "@ant-design/icons";
import { useNavigate, useOutletContext } from "react-router-dom";
import type { WorkspaceOutletContext } from "../../layouts/WorkspaceLayout/WorkspaceLayout";
import { ROUTES } from "../../router/paths";
import AskComposer from "./components/AskComposer";
import { CatalogDrawer, FeedbackDialog } from "./components/AskDialogs";
import MessageTimeline from "./components/MessageTimeline";
import WelcomePanel from "./components/WelcomePanel";
import { useAskResources } from "./hooks/useAskResources";
import { useConversationSession } from "./hooks/useConversationSession";
import { useVoiceRecorder } from "./hooks/useVoiceRecorder";
import styles from "./AskPage.module.scss";

export default function AskPage() {
  const navigate = useNavigate();
  const { conversations, refreshConversations } = useOutletContext<WorkspaceOutletContext>();
  const resources = useAskResources();
  const session = useConversationSession(refreshConversations, resources.refreshCommon);
  const [catalogOpen, setCatalogOpen] = useState(false);
  const [feedbackMessageId, setFeedbackMessageId] = useState<string | null>(null);
  const [quickOpen, setQuickOpen] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);
  const composerRef = useRef<TextAreaRef>(null);
  const voice = useVoiceRecorder((text) =>
    session.setDraft(session.draft.trim() ? `${session.draft.trim()} ${text}` : text),
  );

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [session.messages, session.stage, session.liveAnalysis]);

  useEffect(() => {
    if (session.loadingConversation || !session.messages.length) return;
    const frame = window.requestAnimationFrame(() =>
      endRef.current?.scrollIntoView({ block: "end" }),
    );
    const afterCharts = window.setTimeout(
      () => endRef.current?.scrollIntoView({ block: "end" }),
      450,
    );
    return () => {
      window.cancelAnimationFrame(frame);
      window.clearTimeout(afterCharts);
    };
  }, [session.loadingConversation, session.messages.length]);

  const title =
    conversations.find((item) => item.id === session.conversationId)?.title ?? "AI 智能问数";
  const error = session.error || resources.error;

  return (
    <div className={styles["ask-page"]}>
      <header className={styles["ask-header"]}>
        <div>
          <MessageOutlined />
          <span>{title}</span>
        </div>
        <Tooltip title="查看模型连接状态">
          <Button size="small" type="text" onClick={() => navigate(ROUTES.settings)}>
            <i className={resources.catalog?.model.configured ? styles["is-ready"] : undefined} />
            {resources.settings.llm_model}
          </Button>
        </Tooltip>
      </header>
      {error && (
        <div className={styles["ask-page__error"]}>
          <Alert
            type="error"
            showIcon
            closable
            message={error}
            onClose={() => {
              session.dismissError();
              resources.dismissError();
            }}
          />
        </div>
      )}
      <main className={styles["ask-content"]}>
        <div className={styles["ask-scroll"]}>
          {session.loadingConversation || (resources.loading && !resources.catalog) ? (
            <div className={styles["ask-loading"]}>
              <Spin />
            </div>
          ) : session.messages.length ? (
            <MessageTimeline
              messages={session.messages}
              favorites={resources.favorites}
              busy={session.busy}
              stage={session.stage}
              endRef={endRef}
              onFavorite={resources.toggleFavorite}
              onAsk={(question) => void session.ask(question)}
              onEdit={(question) => {
                session.setDraft(question);
                composerRef.current?.focus({ cursor: "end" });
              }}
              onRetry={session.retry}
              onFeedback={setFeedbackMessageId}
            />
          ) : (
            <WelcomePanel
              catalog={resources.catalog}
              settings={resources.settings}
              questions={resources.questions}
              busy={session.busy}
              onAsk={(question) => void session.ask(question)}
              onCatalog={() => setCatalogOpen(true)}
            />
          )}
        </div>
      </main>
      <AskComposer
        inputRef={composerRef}
        draft={session.draft}
        hasMessages={session.messages.length > 0}
        busy={session.busy}
        loadingConversation={session.loadingConversation}
        catalog={resources.catalog}
        settings={resources.settings}
        commonQuestions={resources.commonQuestions}
        favorites={resources.favorites}
        quickOpen={quickOpen}
        recording={voice.recording}
        transcribing={voice.transcribing}
        onDraft={session.setDraft}
        onAsk={() => void session.ask()}
        onStop={session.stop}
        onToggleRecording={() => void voice.toggle()}
        onQuickOpen={setQuickOpen}
        onCatalog={() => setCatalogOpen(true)}
        onRemoveCommon={resources.removeCommonQuestion}
        onRemoveFavorite={resources.removeFavorite}
      />
      <CatalogDrawer
        catalog={resources.catalog}
        open={catalogOpen}
        onClose={() => setCatalogOpen(false)}
      />
      <FeedbackDialog messageId={feedbackMessageId} onClose={() => setFeedbackMessageId(null)} />
    </div>
  );
}
