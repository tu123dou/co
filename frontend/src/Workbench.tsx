import { useEffect, useRef, useState } from "react";
import {
  Alert,
  Button,
  Drawer,
  Dropdown,
  Empty,
  Input,
  Modal,
  Popconfirm,
  Spin,
  Table,
  Tabs,
  Tag,
  Tooltip,
  message,
} from "antd";
import {
  BarChartOutlined,
  PlusOutlined,
  MessageOutlined,
  StarOutlined,
  DatabaseOutlined,
  SettingOutlined,
  LogoutOutlined,
  MoreOutlined,
  ArrowUpOutlined,
  StopOutlined,
  ArrowRightOutlined,
  CheckCircleOutlined,
  LineChartOutlined,
  PieChartOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  SearchOutlined,
  ApartmentOutlined,
  HistoryOutlined,
} from "@ant-design/icons";
import { api, post } from "./api";

import type { Msg } from "./types";
import Answer from "./QueryAnswer";

export default function Workbench({
  user,
  onLogout,
}: {
  user: any;
  onLogout: () => void;
}) {
  const [catalog, setCatalog] = useState<any>(null),
    [conversations, setConversations] = useState<any[]>([]),
    [cid, setCid] = useState<string | null>(null),
    [msgs, setMsgs] = useState<Msg[]>([]),
    [input, setInput] = useState(""),
    [busy, setBusy] = useState(false),
    [stage, setStage] = useState(""),
    [detail, setDetail] = useState(""),
    [drawer, setDrawer] = useState(""),
    [favorites, setFavorites] = useState<any[]>([]),
    [search, setSearch] = useState(""),
    [error, setError] = useState(""),
    [collapsed, setCollapsed] = useState(false),
    [feedback, setFeedback] = useState(""),
    [remark, setRemark] = useState(""),
    [rename, setRename] = useState<any>(null),
    [renameText, setRenameText] = useState(""),
    [testing, setTesting] = useState(false),
    [loadingChat, setLoadingChat] = useState(false);
  const abort = useRef<AbortController | null>(null),
    end = useRef<HTMLDivElement>(null),
    sending = useRef(false);
  const refresh = () => api("/conversations").then(setConversations);
  useEffect(() => {
    Promise.all([
      api("/catalog").then(setCatalog),
      refresh(),
      api("/favorites").then(setFavorites),
    ]).catch((e) => setError(e.message));
  }, []);
  useEffect(() => {
    end.current?.scrollIntoView({ behavior: "smooth" });
  }, [msgs, stage]);
  async function loadConversation(id: string) {
    if (sending.current) return;
    setLoadingChat(true);
    setError("");
    try {
      const c = await api("/conversations/" + id);
      setCid(id);
      setMsgs(c.messages);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoadingChat(false);
    }
  }
  async function ask(question = input) {
    if (sending.current || !question.trim()) return;
    if (question === "__retry__") {
      question =
        [...msgs].reverse().find((m) => m.role === "user")?.content || "";
      if (!question) return;
    }
    sending.current = true;
    setBusy(true);
    setInput("");
    setError("");
    setStage("理解问题");
    setDetail("正在连接问数服务");
    const controller = new AbortController();
    abort.current = controller;
    let id = cid;
    try {
      if (!id) {
        const c = await post("/conversations");
        id = c.id;
        setCid(id);
      }
      setMsgs((m) => [
        ...m,
        { id: crypto.randomUUID(), role: "user", content: question },
      ]);
      const res = await fetch("/api/conversations/" + id + "/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
        signal: controller.signal,
      });
      if (!res.ok) {
        const d = await res.json();
        throw new Error(d.detail || "问数失败");
      }
      const reader = res.body!.getReader(),
        decoder = new TextDecoder();
      let buffer = "";
      let gotResult = false;
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";
        for (const line of lines) {
          if (!line.trim()) continue;
          const event = JSON.parse(line);
          if (event.type === "status") {
            setStage(event.stage);
            setDetail(event.detail);
          }
          if (event.type === "result") {
            gotResult = true;
            setMsgs((m) => [...m, event.message]);
          }
        }
      }
      if (!gotResult) throw new Error("连接中断，未收到完整结果，请重试");
    } catch (e) {
      if ((e as Error).name === "AbortError") {
        setMsgs((m) => [
          ...m,
          {
            id: crypto.randomUUID(),
            role: "assistant",
            content: "本次生成已停止。",
            result: { status: "cancelled" },
          },
        ]);
      } else {
        setError((e as Error).message);
        setInput(question);
      }
    } finally {
      sending.current = false;
      setBusy(false);
      abort.current = null;
      refresh().catch(() => {});
    }
  }
  const favorite = async (q: string) => {
    try {
      await post("/favorites", { question: q });
      setFavorites(await api("/favorites"));
      message.success("已收藏问题");
    } catch (e) {
      message.error((e as Error).message);
    }
  };
  const actions = (c: any) => [
    {
      key: "pin",
      label: c.pinned ? "取消置顶" : "置顶",
      onClick: () =>
        api("/conversations/" + c.id, {
          method: "PATCH",
          body: JSON.stringify({ pinned: !c.pinned }),
        })
          .then(refresh)
          .catch((e) => message.error(e.message)),
    },
    {
      key: "rename",
      label: "重命名",
      onClick: () => {
        setRename(c);
        setRenameText(c.title);
      },
    },
    {
      key: "delete",
      label: "删除会话",
      danger: true,
      onClick: () =>
        Modal.confirm({
          title: "删除这个会话？",
          content: "会话、回答和相关反馈将一起删除。",
          okText: "删除",
          cancelText: "取消",
          okButtonProps: { danger: true },
          onOk: async () => {
            await api("/conversations/" + c.id, { method: "DELETE" });
            if (cid === c.id) {
              setCid(null);
              setMsgs([]);
            }
            await refresh();
          },
        }),
    },
  ];
  return (
    <div className={"workbench " + (collapsed ? "is-collapsed" : "")}>
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-icon">
            <BarChartOutlined />
          </span>
          {!collapsed && (
            <span>
              经管之星<small>经营数据工作台</small>
            </span>
          )}
        </div>
        <Button
          className="new-chat"
          aria-label="开启新对话"
          type="primary"
          icon={<PlusOutlined />}
          disabled={busy}
          onClick={() => {
            setCid(null);
            setMsgs([]);
            setError("");
            setInput("");
          }}
        >
          {!collapsed && "开启新对话"}
        </Button>
        <nav>
          <button
            className="nav-item mobile-history"
            aria-label="历史会话"
            onClick={() => setDrawer("history")}
          >
            <HistoryOutlined />
          </button>
          <button className="nav-item active" onClick={() => setDrawer("")}>
            <MessageOutlined />
            {!collapsed && "智能问数"}
          </button>
          <button className="nav-item" onClick={() => setDrawer("favorites")}>
            <StarOutlined />
            {!collapsed && (
              <>
                收藏问题<span className="nav-count">{favorites.length}</span>
              </>
            )}
          </button>
          <button className="nav-item" onClick={() => setDrawer("catalog")}>
            <DatabaseOutlined />
            {!collapsed && "数据与指标"}
          </button>
        </nav>
        {!collapsed && (
          <div className="history">
            <div className="history-heading">
              最近会话<span>{conversations.length}</span>
            </div>
            <Input
              className="history-search"
              prefix={<SearchOutlined />}
              placeholder="搜索会话"
              variant="borderless"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              allowClear
            />
            <div className="history-list">
              {conversations
                .filter((c) => c.title.includes(search))
                .map((c) => (
                  <div
                    key={c.id}
                    className={
                      "history-item " + (cid === c.id ? "selected" : "")
                    }
                  >
                    <button
                      disabled={busy}
                      onClick={() => loadConversation(c.id)}
                      title={c.title}
                    >
                      {c.pinned && <span className="pin-dot" />}
                      {c.title}
                    </button>
                    <Dropdown
                      menu={{ items: actions(c) }}
                      trigger={["click"]}
                      disabled={busy}
                    >
                      <Button
                        size="small"
                        type="text"
                        icon={<MoreOutlined />}
                        aria-label={"管理会话 " + c.title}
                      />
                    </Dropdown>
                  </div>
                ))}
              {!conversations.length && (
                <p className="history-empty">你的分析记录会保存在这里</p>
              )}
            </div>
          </div>
        )}
        <div className="sidebar-bottom">
          <button className="nav-item" onClick={() => setDrawer("settings")}>
            <SettingOutlined />
            {!collapsed && "工作台设置"}
          </button>
          <div className="user-row">
            <span className="avatar">管</span>
            {!collapsed && (
              <>
                <div>
                  {user.display_name}
                  <small>本地工作空间</small>
                </div>
                <Tooltip title="退出登录">
                  <Button
                    type="text"
                    icon={<LogoutOutlined />}
                    disabled={busy}
                    onClick={onLogout}
                  />
                </Tooltip>
              </>
            )}
          </div>
        </div>
      </aside>
      <main className="main">
        <header className="topbar">
          <div>
            <Button
              type="text"
              icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
              onClick={() => setCollapsed(!collapsed)}
              aria-label="切换侧栏"
            />
            <span className="breadcrumb">
              工作空间 <span>/</span> <b>智能问数</b>
            </span>
          </div>
          <div className="topbar-right">
            <Tag color="blue" bordered={false}>
              模拟经营数据
            </Tag>
            <span className="dataset-date">
              更新至 {catalog?.dataset?.cutoff_date || "—"}
            </span>
          </div>
        </header>
        <div className="conversation-top">
          <div>
            <MessageOutlined />
            <span>
              {conversations.find((c) => c.id === cid)?.title || "AI 智能问数"}
            </span>
          </div>
          <Tooltip title="查看模型连接状态">
            <Button
              size="small"
              type="text"
              onClick={() => setDrawer("settings")}
            >
              <span
                className={
                  "model-dot " + (catalog?.model.configured ? "ready" : "")
                }
              />
              {catalog?.model.name || "qwen3.8-max"}
            </Button>
          </Tooltip>
        </div>
        {error && (
          <div className="page-error">
            <Alert
              type="error"
              message={error}
              closable
              onClose={() => setError("")}
              showIcon
            />
          </div>
        )}
        <div className="chat-scroll">
          {loadingChat ? (
            <div className="chat-loading">
              <Spin />
            </div>
          ) : !msgs.length ? (
            <div className="welcome">
              <div className="welcome-mark">
                <BarChartOutlined />
              </div>
              <span className="eyebrow">你的经营分析伙伴</span>
              <h1>你好，今天想了解哪些数据？</h1>
              <p>从收入趋势到目标达成，用自然语言探索你的经营数据。</p>
              <div className="capability-tags">
                <span>
                  <CheckCircleOutlined /> 真实 SQL 取数
                </span>
                <span>
                  <LineChartOutlined /> 图表自动呈现
                </span>
                <span>
                  <MessageOutlined /> 支持连续追问
                </span>
              </div>
              <div className="suggestion-heading">
                <span>从一个问题开始</span>
                <span>
                  你可以这样问 <ArrowRightOutlined />
                </span>
              </div>
              <div className="question-grid">
                {(
                  catalog?.examples || [
                    "今年各经营单元确认收入排名",
                    "今年各产品线的收入占比",
                    "华东区今年按月收入趋势，与去年同期相比",
                    "2026年8月各产品线毛利率",
                    "今年各区域收入目标达成率",
                    "2026年8月回款额比上个月变化多少",
                  ]
                ).map((q: string, i: number) => (
                  <button
                    key={q}
                    disabled={busy || !catalog}
                    onClick={() => ask(q)}
                  >
                    <span className={"question-icon qi-" + i}>
                      {
                        [
                          <BarChartOutlined />,
                          <PieChartOutlined />,
                          <LineChartOutlined />,
                          <ApartmentOutlined />,
                          <CheckCircleOutlined />,
                          <DatabaseOutlined />,
                        ][i]
                      }
                    </span>
                    <span>{q}</span>
                    <ArrowRightOutlined />
                  </button>
                ))}
              </div>
              <div className="data-context">
                <DatabaseOutlined />
                <span>
                  企业软件与服务 ·{" "}
                  {catalog?.dataset?.counts?.contracts?.toLocaleString() || "—"}{" "}
                  份合同 · 10 个经营单元
                </span>
                <button onClick={() => setDrawer("catalog")}>
                  查看数据范围
                </button>
              </div>
            </div>
          ) : (
            <div className="message-list">
              {msgs.map((m) =>
                m.role === "user" ? (
                  <div key={m.id} className="user-message">
                    <div>{m.content}</div>
                    <Tooltip title="收藏问题">
                      <Button
                        type="text"
                        size="small"
                        icon={<StarOutlined />}
                        onClick={() => favorite(m.content)}
                      />
                    </Tooltip>
                  </div>
                ) : (
                  <Answer
                    key={m.id}
                    msg={m}
                    onAsk={(q) => ask(q)}
                    onFeedback={setFeedback}
                  />
                ),
              )}
              {busy && (
                <div className="assistant-row processing">
                  <div className="assistant-icon">
                    <BarChartOutlined />
                  </div>
                  <div>
                    <div>
                      <Spin size="small" />
                      <strong>{stage}</strong>
                    </div>
                    <p>{detail}</p>
                    <div className="progress-steps">
                      {["理解问题", "执行取数", "整理结果"].map((s, i) => (
                        <span
                          key={s}
                          className={
                            ["理解问题", "执行取数", "整理结果"].indexOf(
                              stage,
                            ) >= i
                              ? "current"
                              : ""
                          }
                        >
                          {i + 1} {s}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              )}
              <div ref={end} />
            </div>
          )}
        </div>
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
              <button onClick={() => setDrawer("catalog")}>
                <DatabaseOutlined /> 企业经营数据 <span>12 张业务表</span>
              </button>
              <div>
                <span className="enter-hint">
                  Enter 发送 · Shift + Enter 换行
                </span>
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
            数据由系统模拟生成，仅用于产品演示与验证。相对时间以数据截止日为准，重要决策请核对口径。
          </p>
        </footer>
      </main>
      <Drawer
        title={
          drawer === "history"
            ? "历史会话"
            : drawer === "catalog"
              ? "数据与指标"
              : drawer === "favorites"
                ? "收藏问题"
                : "工作台设置"
        }
        open={!!drawer}
        onClose={() => setDrawer("")}
        width={600}
      >
        {drawer === "history" && (
          <div className="favorite-list">
            {conversations.length ? (
              conversations.map((c) => (
                <div key={c.id}>
                  <button
                    disabled={busy}
                    onClick={() => {
                      setDrawer("");
                      loadConversation(c.id);
                    }}
                  >
                    {c.title}
                    <ArrowRightOutlined />
                  </button>
                </div>
              ))
            ) : (
              <Empty description="暂无会话记录" />
            )}
          </div>
        )}
        {drawer === "catalog" && catalog && (
          <>
            <Alert
              type="info"
              message="企业软件与服务 · 模拟经营数据"
              description={`覆盖 ${catalog.dataset.start_date} 至 ${catalog.dataset.cutoff_date}，固定种子生成，所有金额采用不含税管理口径。`}
              showIcon
            />
            <Tabs
              items={[
                {
                  key: "metrics",
                  label: "指标口径",
                  children: (
                    <div className="metric-list">
                      {Object.entries(catalog.metrics).map(
                        ([key, m]: [string, any]) => (
                          <div key={key}>
                            <h3>
                              {m.name}
                              <Tag>{m.unit}</Tag>
                            </h3>
                            <p>{m.definition}</p>
                            <small>{key} · v1</small>
                          </div>
                        ),
                      )}
                    </div>
                  ),
                },
                {
                  key: "data",
                  label: "数据范围",
                  children: (
                    <>
                      <h3>经营单元</h3>
                      <div className="tag-wrap">
                        {catalog.values.org_unit.map((v: string) => (
                          <Tag key={v}>{v}</Tag>
                        ))}
                      </div>
                      <h3>产品线</h3>
                      <div className="tag-wrap">
                        {catalog.values.product_line.map((v: string) => (
                          <Tag key={v}>{v}</Tag>
                        ))}
                      </div>
                      <h3>数据记录</h3>
                      <Table
                        rowKey="table"
                        size="small"
                        pagination={false}
                        columns={[
                          { title: "数据表", dataIndex: "table" },
                          {
                            title: "记录数",
                            dataIndex: "count",
                            align: "right",
                          },
                        ]}
                        dataSource={Object.entries(catalog.dataset.counts).map(
                          ([table, count]) => ({ table, count }),
                        )}
                      />
                    </>
                  ),
                },
              ]}
            />
          </>
        )}
        {drawer === "favorites" &&
          (favorites.length ? (
            <div className="favorite-list">
              {favorites.map((f) => (
                <div key={f.id}>
                  <button
                    disabled={busy}
                    onClick={() => {
                      setDrawer("");
                      ask(f.question);
                    }}
                  >
                    {f.question}
                    <ArrowRightOutlined />
                  </button>
                  <Popconfirm
                    title="取消收藏这个问题？"
                    onConfirm={async () => {
                      await api("/favorites/" + f.id, { method: "DELETE" });
                      setFavorites(await api("/favorites"));
                    }}
                  >
                    <Button type="text" size="small">
                      取消收藏
                    </Button>
                  </Popconfirm>
                </div>
              ))}
            </div>
          ) : (
            <Empty description="点击问题旁的星标，即可收藏" />
          ))}
        {drawer === "settings" && (
          <div className="settings">
            <h3>模型连接</h3>
            <p>模型：{catalog?.model.name || "qwen3.8-max"}</p>
            <Tag color={catalog?.model.configured ? "green" : "orange"}>
              {catalog?.model.configured
                ? "API Key 已配置"
                : "尚未配置 API Key"}
            </Tag>
            <p>模型凭据仅保存在后端环境配置，不向浏览器返回。</p>
            <Button
              loading={testing}
              onClick={async () => {
                setTesting(true);
                try {
                  const r = await post("/model/test");
                  message.success(
                    `连接成功，耗时 ${(r.duration_ms / 1000).toFixed(1)} 秒`,
                  );
                } catch (e) {
                  message.error((e as Error).message);
                } finally {
                  setTesting(false);
                }
              }}
            >
              测试模型连接
            </Button>
            <hr />
            <h3>关于工作台</h3>
            <p>经管之星 v0.1 · 本地部署</p>
            <p>PostgreSQL 业务数据 · 只读问数查询</p>
            <p>数据版本：{catalog?.dataset.version}</p>
            <Alert
              message="支持范围"
              description="支持指标汇总、排名、趋势、占比、同比/环比及目标达成。复杂归因、预测、应收账龄和产品线回款分摊暂不支持。"
              type="info"
            />
          </div>
        )}
      </Drawer>
      <Modal
        title="回答反馈"
        open={!!feedback}
        onCancel={() => {
          setFeedback("");
          setRemark("");
        }}
        okText="提交反馈"
        cancelText="取消"
        okButtonProps={{ disabled: !remark.trim() }}
        onOk={async () => {
          try {
            await post("/feedbacks", { message_id: feedback, comment: remark });
            message.success("反馈已保存");
            setFeedback("");
            setRemark("");
          } catch (e) {
            message.error((e as Error).message);
          }
        }}
      >
        <p>请说明有疑问的数据或口径，帮助后续核查。</p>
        <Input.TextArea
          value={remark}
          onChange={(e) => setRemark(e.target.value)}
          maxLength={1000}
          rows={4}
          placeholder="例如：收入统计范围与预期不一致…"
        />
      </Modal>
      <Modal
        title="重命名会话"
        open={!!rename}
        onCancel={() => setRename(null)}
        okText="保存"
        cancelText="取消"
        okButtonProps={{ disabled: !renameText.trim() }}
        onOk={async () => {
          try {
            await api("/conversations/" + rename.id, {
              method: "PATCH",
              body: JSON.stringify({ title: renameText.trim() }),
            });
            setRename(null);
            await refresh();
          } catch (e) {
            message.error((e as Error).message);
          }
        }}
      >
        <Input
          value={renameText}
          onChange={(e) => setRenameText(e.target.value)}
          maxLength={100}
        />
      </Modal>
    </div>
  );
}
