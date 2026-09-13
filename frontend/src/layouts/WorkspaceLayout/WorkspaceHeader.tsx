import { Button, Tag } from "antd";
import { MenuFoldOutlined, MenuUnfoldOutlined } from "@ant-design/icons";
import type { WorkspacePage } from "../../router/paths";

const PAGE_TITLES: Record<WorkspacePage, [string, string]> = {
  ask: ["工作空间", "智能问数"], settings: ["系统管理", "应用配置"], feedback: ["反馈管理", "回复校对"],
};

/** 管理后台公共顶部栏。 */
export default function WorkspaceHeader({ page, collapsed, onToggleMenu, cutoffDate }: {
  page: WorkspacePage; collapsed: boolean; onToggleMenu: () => void; cutoffDate?: string;
}) {
  const [section, title] = PAGE_TITLES[page];
  return <header className="topbar">
    <div>
      <Button type="text" icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
        onClick={onToggleMenu} aria-label="切换侧栏" />
      <span className="breadcrumb">{section} <span>/</span> <b>{title}</b></span>
    </div>
    <div className="topbar-right">
      <Tag color="blue" bordered={false}>经营数据</Tag>
      <span className="dataset-date">更新至 {cutoffDate || "—"}</span>
    </div>
  </header>;
}
