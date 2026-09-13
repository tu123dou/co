import { Alert, Button, Collapse, Tooltip, message } from "antd";
import { ArrowRightOutlined, BarChartOutlined, CheckCircleOutlined, CopyOutlined, FlagOutlined, LoadingOutlined, PauseCircleOutlined, ReloadOutlined, SoundOutlined } from "@ant-design/icons";
import type { AnalysisStep, Msg, QueryResult } from "../../../../models/query";
import useSpeechPlayback from "../../hooks/useSpeechPlayback";
import ResultCard from "./ResultCard";

function AnalysisProcess({ process }: { process: AnalysisStep[] }) {
  if (!process.length) return null;
  return <Collapse className="analysis-process" items={[{ key: "process", label: "查看分析过程", children:
    <div className="analysis-steps">{process.map((step, index) => <div className="analysis-step" key={step.key}>
      <div className="analysis-step-index">{index + 1}</div><div className="analysis-step-body">
        <h4>{step.title}<span className={`analysis-step-status ${step.status || "complete"}`}>{step.status === "running" ? "进行中" : "已完成"}</span></h4>
        {(step.items || []).map((item, itemIndex) => <p key={itemIndex}>{item}</p>)}
        {(step.executions || []).map((execution, sqlIndex) => <div className="analysis-sql" key={sqlIndex}>
          <details className="analysis-sql-details"><summary>{execution.name}</summary><pre>{execution.executable_sql}</pre></details>
          <details className="analysis-sql-details"><summary>取数逻辑</summary><pre>{execution.business_sql}</pre></details>
        </div>)}
      </div>
    </div>)}</div>
  }]} />;
}

function AnswerActions({ msg, result, speech, onFeedback }: {
  msg: Msg; result: QueryResult; speech: ReturnType<typeof useSpeechPlayback>; onFeedback: (id: string) => void;
}) {
  const responseTime = result.completed_at || msg.created_at;
  return <div className="answer-actions"><div>
    <Tooltip title="复制结论"><Button type="text" icon={<CopyOutlined />} aria-label="复制结论"
      onClick={() => navigator.clipboard.writeText(msg.content).then(() => message.success("已复制"))} /></Tooltip>
    <Tooltip title="反馈问题"><Button type="text" icon={<FlagOutlined />} aria-label="反馈问题" onClick={() => onFeedback(msg.id)} /></Tooltip>
    <Tooltip title={speech.playing ? "暂停播放" : "播放回答"}><Button type="text"
      icon={speech.loading ? <LoadingOutlined spin /> : speech.playing ? <PauseCircleOutlined /> : <SoundOutlined />}
      aria-label={speech.playing ? "暂停播放" : "播放回答"} disabled={speech.loading} onClick={speech.toggle} /></Tooltip>
  </div><span className="answer-meta">耗时 {(result.duration_ms / 1000).toFixed(1)}s
    {result.usage?.total_tokens != null && ` · Token ${result.usage.total_tokens}`}
    {responseTime && ` · ${new Date(responseTime).toLocaleTimeString("zh-CN", { hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit" })}`}
  </span></div>;
}

export default function QueryAnswer({ msg, onAsk, onRetry, onFeedback }: {
  msg: Msg; onAsk: (question: string) => void; onRetry: () => void; onFeedback: (id: string) => void;
}) {
  const speech = useSpeechPlayback(msg.content);
  const result = msg.result;

  if (result?.status !== "success") return <div className="assistant-row">
    <div className="assistant-icon"><BarChartOutlined /></div>
    <div className="answer-message">
      <strong>经管之星 <span>AI 问数助手</span></strong>
      <Alert type={result?.status === "error" ? "error" : "info"} message={msg.content} showIcon />
      {result?.status === "error" ? <Button size="small" icon={<ReloadOutlined />} onClick={onRetry}>重新尝试</Button>
        : <Button size="small" icon={speech.loading ? <LoadingOutlined spin /> : speech.playing ? <PauseCircleOutlined /> : <SoundOutlined />}
            disabled={speech.loading} onClick={speech.toggle}>{speech.playing ? "暂停播放" : "播放回答"}</Button>}
    </div>
  </div>;

  return <div className="assistant-row">
    <div className="assistant-icon"><BarChartOutlined /></div>
    <div className="answer-message">
      <div className="answer-byline"><strong>经管之星</strong><span>AI 问数助手</span>
        <span className="verified"><CheckCircleOutlined /> 已核对取数</span></div>
      <AnalysisProcess process={result.analysis_process || []} />
      <p className="answer-text">{msg.content}</p>
      <ResultCard messageId={msg.id} result={result} />
      <AnswerActions msg={msg} result={result} speech={speech} onFeedback={onFeedback} />
      <div className="followups">{(result.suggestions || []).map((question) => <button key={question} onClick={() => onAsk(question)}>
        {question}<ArrowRightOutlined />
      </button>)}</div>
    </div>
  </div>;
}
