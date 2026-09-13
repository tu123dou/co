import { Button, Dropdown, Input, Tooltip } from "antd";
import { BarChartOutlined, ControlOutlined, ExclamationCircleOutlined, HistoryOutlined, LogoutOutlined, MessageOutlined, MoreOutlined, PlusOutlined, SearchOutlined } from "@ant-design/icons";
import type { CurrentUser } from "../../api/auth";
import type { WorkspacePage } from "../../router/paths";

export default function WorkspaceMenu(props: {
  collapsed: boolean; busy: boolean; page: WorkspacePage; user: CurrentUser;
  conversations: any[]; currentConversationId: string | null; search: string;
  setSearch: (value: string) => void; setDrawer: (value: string) => void;
  setPage: (page: WorkspacePage) => void; onNewChat: () => void;
  loadConversation: (id: string) => void; actions: (conversation: any) => any[];
  handleConversationAction: (conversation: any, key: string) => void; onLogout: () => void;
}) {
  const { collapsed, busy, page, user, conversations, currentConversationId: cid, search, setSearch, setDrawer, setPage, onNewChat, loadConversation, actions, handleConversationAction, onLogout } = props;
  return (
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
          onClick={onNewChat}
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
          <button className={"nav-item " + (page === "ask" ? "active" : "")} onClick={() => { setPage("ask"); setDrawer(""); }}>
            <MessageOutlined />
            {!collapsed && "智能问数"}
          </button>
          <button className={"nav-item " + (page === "settings" ? "active" : "")} onClick={() => setPage("settings")}>
            <ControlOutlined />
            {!collapsed && "应用配置"}
          </button>
          <button className={"nav-item " + (page === "feedback" ? "active" : "")} onClick={() => setPage("feedback")}>
            <ExclamationCircleOutlined />
            {!collapsed && "回复校对"}
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
                      menu={{
                        items: actions(c),
                        onClick: (info) => handleConversationAction(c, info.key),
                      }}
                      trigger={["click"]}
                      disabled={busy}
                    >
                      <Button
                        size="small"
                        type="text"
                        icon={<MoreOutlined />}
                        aria-label={"管理会话 " + c.title}
                        onClick={(event) => event.stopPropagation()}
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
  );
}
