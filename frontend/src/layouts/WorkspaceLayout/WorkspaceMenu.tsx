import { Button, Dropdown, Input, Tooltip, type MenuProps } from "antd";
import {
  BarChartOutlined,
  ControlOutlined,
  ExclamationCircleOutlined,
  HistoryOutlined,
  LogoutOutlined,
  MessageOutlined,
  MoreOutlined,
  PlusOutlined,
  SearchOutlined,
} from "@ant-design/icons";
import type { CurrentUser } from "../../api/auth";
import type { ConversationSummary } from "../../api/conversations";
import type { WorkspacePage } from "../../router/paths";
import styles from "./WorkspaceLayout.module.scss";

export default function WorkspaceMenu(props: {
  collapsed: boolean;
  busy: boolean;
  page: WorkspacePage;
  user: CurrentUser;
  conversations: ConversationSummary[];
  currentConversationId: string | null;
  search: string;
  setSearch: (value: string) => void;
  setDrawer: (value: string) => void;
  setPage: (page: WorkspacePage) => void;
  onNewChat: () => void;
  loadConversation: (id: string) => void;
  actions: (conversation: ConversationSummary) => NonNullable<MenuProps["items"]>;
  handleConversationAction: (conversation: ConversationSummary, key: string) => void;
  onLogout: () => void;
}) {
  const {
    collapsed,
    busy,
    page,
    user,
    conversations,
    currentConversationId: cid,
    search,
    setSearch,
    setDrawer,
    setPage,
    onNewChat,
    loadConversation,
    actions,
    handleConversationAction,
    onLogout,
  } = props;
  const avatarText = Array.from(user.display_name.trim())[0] ?? "用";
  const navClass = (target: WorkspacePage) =>
    `${styles.navItem} ${page === target ? styles.active : ""}`;
  return (
    <aside className={`${styles.sidebar} ${collapsed ? styles.collapsed : ""}`}>
      <div className={styles.brand}>
        <span className={styles.brandIcon}>
          <BarChartOutlined />
        </span>
        {!collapsed && (
          <span>
            经管之星<small>经营数据工作台</small>
          </span>
        )}
      </div>
      <Button
        className={styles.newChat}
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
          className={`${styles.navItem} ${styles.mobileHistory}`}
          aria-label="历史会话"
          onClick={() => setDrawer("history")}
        >
          <HistoryOutlined />
        </button>
        <button
          className={navClass("ask")}
          onClick={() => {
            setPage("ask");
            setDrawer("");
          }}
        >
          <MessageOutlined />
          {!collapsed && "智能问数"}
        </button>
        <button className={navClass("settings")} onClick={() => setPage("settings")}>
          <ControlOutlined />
          {!collapsed && "应用配置"}
        </button>
        <button className={navClass("feedback")} onClick={() => setPage("feedback")}>
          <ExclamationCircleOutlined />
          {!collapsed && "回复校对"}
        </button>
      </nav>
      {!collapsed && (
        <div className={styles.history}>
          <div className={styles.historyHeading}>
            最近会话<span>{conversations.length}</span>
          </div>
          <Input
            className={styles.historySearch}
            prefix={<SearchOutlined />}
            placeholder="搜索会话"
            variant="borderless"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            allowClear
          />
          <div className={styles.historyList}>
            {conversations
              .filter((c) => c.title.includes(search))
              .map((c) => (
                <div
                  key={c.id}
                  className={`${styles.historyItem} ${cid === c.id ? styles.selected : ""}`}
                >
                  <button disabled={busy} onClick={() => loadConversation(c.id)} title={c.title}>
                    {c.pinned && <span className={styles.pinDot} />}
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
                      className={styles.historyAction}
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
              <p className={styles.historyEmpty}>你的分析记录会保存在这里</p>
            )}
          </div>
        </div>
      )}
      <div className={styles.sidebarBottom}>
        <div className={styles.userRow}>
          <span className={styles.avatar}>{avatarText}</span>
          {!collapsed && (
            <>
              <div>
                {user.display_name}
                {/* <small>本地工作空间</small> */}
              </div>
              <Tooltip title="退出登录">
                <Button type="text" icon={<LogoutOutlined />} disabled={busy} onClick={onLogout} />
              </Tooltip>
            </>
          )}
        </div>
      </div>
    </aside>
  );
}
