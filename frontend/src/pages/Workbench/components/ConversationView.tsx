import type { RefObject } from "react";
import { Alert, Button, Spin, Tooltip } from "antd";
import { ApartmentOutlined, ArrowRightOutlined, BarChartOutlined, CheckCircleOutlined, DatabaseOutlined, LineChartOutlined, MessageOutlined, PieChartOutlined, ReloadOutlined, StarFilled, StarOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import { ROUTES } from "../../../router/paths";
import type { Msg } from "../../../models/query";
import type { FavoriteQuestion } from "../../../models/workbench";
import { useWorkbench } from "../WorkbenchContext";
import QueryAnswer from "./QueryAnswer/QueryAnswer";

const QUESTION_ICONS = [BarChartOutlined, PieChartOutlined, LineChartOutlined, ApartmentOutlined, CheckCircleOutlined, DatabaseOutlined];

function ConversationGuide() {
  const { session, openCatalog } = useWorkbench();
  const { catalog, workbenchSettings: settings, visibleStarterQuestions: questions, questionPool, busy, ask } = session;
  const changePage = () => session.setQuestionOffset((current) => (current + 6) % questionPool.length);
  return <div className={`welcome ${settings.welcome_enabled ? "" : "welcome-disabled"}`}>
    {settings.welcome_enabled && <>
      <div className="welcome-mark"><BarChartOutlined /></div><span className="eyebrow">你的经营分析伙伴</span>
      <h1>{settings.welcome_title}</h1><p>{settings.welcome_message}</p>
      <div className="capability-tags"><span><CheckCircleOutlined /> 真实 SQL 取数</span><span><LineChartOutlined /> 图表自动呈现</span><span><MessageOutlined /> 支持连续追问</span></div>
      {questions.length > 0 && <><div className="suggestion-heading"><span>从一个问题开始</span>
        <button className="suggestion-refresh" disabled={questionPool.length <= 6} onClick={changePage}><ReloadOutlined /> 换一批</button></div>
        <div className="question-grid">{questions.map((question, index) => {
          const Icon = QUESTION_ICONS[index % QUESTION_ICONS.length];
          return <button key={question} disabled={busy || !catalog} onClick={() => ask(question)}>
            <span className={`question-icon qi-${index % 6}`}><Icon /></span><span>{question}</span><ArrowRightOutlined />
          </button>;
        })}</div></>}
    </>}
    <div className="data-context"><DatabaseOutlined />
      <span>企业软件与服务 · {catalog?.dataset.counts.contracts?.toLocaleString() || "—"} 份合同 · 10 个经营单元</span>
      <button onClick={openCatalog}>查看数据范围</button>
    </div>
  </div>;
}

function MessageList({ messages, favorites, endRef }: { messages: Msg[]; favorites: FavoriteQuestion[]; endRef: RefObject<HTMLDivElement | null> }) {
  const { session, openFeedback } = useWorkbench();
  return <div className="message-list">
    {messages.map((item) => item.role === "user" ? <div key={item.id} className="user-message">
      <div>{item.content}</div><Tooltip title={favorites.some((favorite) => favorite.question === item.content) ? "取消收藏" : "收藏问题"}>
        <Button type="text" size="small" className={favorites.some((favorite) => favorite.question === item.content) ? "favorite-active" : ""}
          icon={favorites.some((favorite) => favorite.question === item.content) ? <StarFilled /> : <StarOutlined />}
          onClick={() => session.favorite(item.content)} />
      </Tooltip>
    </div> : <QueryAnswer key={item.id} msg={item} onAsk={session.ask} onRetry={session.retry} onFeedback={openFeedback} />)}
    {session.busy && <div className="assistant-row processing"><div className="assistant-icon"><BarChartOutlined /></div>
      <div className="thinking-state"><div className="thinking-title"><Spin size="small" /><strong>正在思考</strong>
        <span className="thinking-dots" aria-hidden="true"><i /><i /><i /></span></div>
        <p key={`${session.stage}-${session.thinkingIndex}`}>{(session.thinkingCopy[session.stage] || ["正在理解你的问题并准备查询"])[session.thinkingIndex % (session.thinkingCopy[session.stage]?.length || 1)]}</p>
      </div></div>}
    <div ref={endRef} />
  </div>;
}

export default function ConversationView() {
  const navigate = useNavigate();
  const { session } = useWorkbench();
  const title = session.conversations.find((item) => item.id === session.cid)?.title || "AI 智能问数";
  return <>
    <div className="conversation-top"><div><MessageOutlined /><span>{title}</span></div>
      <Tooltip title="查看模型连接状态"><Button size="small" type="text" onClick={() => navigate(ROUTES.settings)}>
        <span className={`model-dot${session.catalog?.model.configured ? " ready" : ""}`} />{session.workbenchSettings.llm_model}
      </Button></Tooltip>
    </div>
    <div className="chat-content">
      {session.error && <div className="page-error"><Alert type="error" message={session.error} closable onClose={() => session.setError("")} showIcon /></div>}
      <div className="chat-scroll">{session.loadingChat ? <div className="chat-loading"><Spin /></div>
        : session.msgs.length ? <MessageList messages={session.msgs} favorites={session.favorites} endRef={session.end} /> : <ConversationGuide />}</div>
    </div>
  </>;
}
