import { useCallback, useEffect, useState } from "react";
import { Drawer, Empty, Input, Modal, message } from "antd";
import { Outlet, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import type { CurrentUser } from "../../api/auth";
import { deleteConversation, listConversations, updateConversation } from "../../api/conversations";
import { getCatalog } from "../../api/workbench";
import { pageFromPath, ROUTES, type WorkspacePage } from "../../router/paths";
import WorkspaceMenu from "./WorkspaceMenu";
import WorkspaceHeader from "./WorkspaceHeader";
import type { ConversationSummary } from "../../api/conversations";
import styles from "./WorkspaceLayout.module.scss";

export type WorkspaceOutletContext = {
  conversations: ConversationSummary[];
  refreshConversations: () => Promise<void>;
};

/** 传统管理后台外壳：只负责公共菜单、顶部栏和业务页面出口。 */
export default function WorkspaceLayout({
  user,
  onLogout,
}: {
  user: CurrentUser;
  onLogout: () => void;
}) {
  const location = useLocation();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const page = pageFromPath(location.pathname) ?? "ask";
  const [collapsed, setCollapsed] = useState(false);
  const [search, setSearch] = useState("");
  const [drawer, setDrawer] = useState("");
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [cutoffDate, setCutoffDate] = useState("");
  const [rename, setRename] = useState<ConversationSummary | null>(null);
  const [renameText, setRenameText] = useState("");
  const refreshConversations = useCallback(async () => {
    setConversations(await listConversations());
  }, []);

  useEffect(() => {
    refreshConversations().catch((error) => message.error(error.message));
    getCatalog()
      .then((catalog) => setCutoffDate(catalog?.dataset?.cutoff_date || ""))
      .catch(() => {});
  }, [refreshConversations]);

  const setPage = (next: WorkspacePage) => navigate(ROUTES[next]);
  const openConversation = (id: string) => {
    setDrawer("");
    navigate(`${ROUTES.ask}?conversation=${encodeURIComponent(id)}`);
  };
  const newConversation = () => {
    setDrawer("");
    navigate(`${ROUTES.ask}?new=${Date.now()}`);
  };
  const handleConversationAction = async (conversation: ConversationSummary, key: string) => {
    if (key === "rename") {
      setRename(conversation);
      setRenameText(conversation.title);
      return;
    }
    try {
      if (key === "pin")
        await updateConversation(conversation.id, { pinned: !conversation.pinned });
      if (key === "delete") {
        await deleteConversation(conversation.id);
        if (searchParams.get("conversation") === conversation.id) newConversation();
      }
      await refreshConversations();
    } catch (error) {
      message.error((error as Error).message);
    }
  };

  return (
    <div className={styles.workbench}>
      <WorkspaceMenu
        collapsed={collapsed}
        busy={false}
        page={page}
        user={user}
        conversations={conversations}
        currentConversationId={searchParams.get("conversation")}
        search={search}
        setSearch={setSearch}
        setDrawer={setDrawer}
        setPage={setPage}
        onNewChat={newConversation}
        loadConversation={openConversation}
        actions={(conversation) => [
          { key: "pin", label: conversation.pinned ? "取消置顶" : "置顶" },
          { key: "rename", label: "重命名" },
          { key: "delete", label: "删除会话", danger: true },
        ]}
        handleConversationAction={handleConversationAction}
        onLogout={onLogout}
      />
      <main className={styles.main}>
        <WorkspaceHeader
          page={page}
          collapsed={collapsed}
          onToggleMenu={() => setCollapsed((value) => !value)}
          cutoffDate={cutoffDate}
        />
        <Outlet
          context={{ conversations, refreshConversations } satisfies WorkspaceOutletContext}
        />
      </main>
      <Drawer
        title="历史会话"
        open={drawer === "history"}
        onClose={() => setDrawer("")}
        width={480}
      >
        {conversations.length ? (
          <div className={styles.favoriteList}>
            {conversations.map((conversation) => (
              <div key={conversation.id}>
                <button onClick={() => openConversation(conversation.id)}>
                  {conversation.title}
                </button>
              </div>
            ))}
          </div>
        ) : (
          <Empty description="暂无会话记录" />
        )}
      </Drawer>
      <Modal
        title="重命名会话"
        open={Boolean(rename)}
        okText="保存"
        cancelText="取消"
        okButtonProps={{ disabled: !renameText.trim() }}
        onCancel={() => setRename(null)}
        onOk={async () => {
          if (!rename) return;
          try {
            await updateConversation(rename.id, { title: renameText.trim() });
            setRename(null);
            await refreshConversations();
          } catch (error) {
            message.error((error as Error).message);
          }
        }}
      >
        <Input
          value={renameText}
          onChange={(event) => setRenameText(event.target.value)}
          maxLength={100}
        />
      </Modal>
    </div>
  );
}
