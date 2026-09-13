import { Button, Input, Tooltip } from "antd";
import { ArrowUpOutlined, AudioOutlined, DatabaseOutlined, LoadingOutlined, StopOutlined } from "@ant-design/icons";
import QuickQuestions from "../QuickQuestions/QuickQuestions";
import { useWorkbench } from "../../WorkbenchContext";

export default function ConversationComposer() {
  const { session, openCatalog } = useWorkbench();
  const { input, setInput, msgs, busy, catalog, loadingChat, quickOpen, setQuickOpen, commonQuestions,
    favorites, workbenchSettings, removeCommonQuestion, removeFavorite, ask, recording, transcribing,
    toggleRecording, abort } = session;
  return (
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
                <button onClick={openCatalog}>
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
  );
}
