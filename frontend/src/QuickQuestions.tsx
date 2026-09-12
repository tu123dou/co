import { Empty, Popover, Tabs, Tag } from "antd";
import { StarOutlined, ThunderboltOutlined } from "@ant-design/icons";
import type { CommonQuestion } from "./workbenchConfig";

export default function QuickQuestions({
  open,
  onOpenChange,
  common,
  favorites,
  commonEnabled,
  onPick,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  common: CommonQuestion[];
  favorites: any[];
  commonEnabled: boolean;
  onPick: (question: string) => void;
}) {
  const list = (rows: Array<{ question: string; success_count?: number }>) =>
    rows.length ? (
      <div className="quick-question-list">
        {rows.map((row) => (
          <button key={row.question} onClick={() => onPick(row.question)}>
            <span>{row.question}</span>
            {row.success_count != null && <Tag>{row.success_count} 次</Tag>}
          </button>
        ))}
      </div>
    ) : (
      <Empty
        image={Empty.PRESENTED_IMAGE_SIMPLE}
        description={commonEnabled ? "暂无符合条件的问题" : "常见问题已关闭"}
      />
    );

  return (
    <Popover
      open={open}
      onOpenChange={onOpenChange}
      placement="topLeft"
      trigger="click"
      title={
        <span className="quick-question-title">
          <ThunderboltOutlined /> 快捷提问
        </span>
      }
      content={
        <Tabs
          className="quick-question-tabs"
          items={[
            {
              key: "common",
              label: "常见",
              children: list(common),
            },
            {
              key: "favorites",
              label: (
                <span>
                  <StarOutlined /> 收藏
                </span>
              ),
              children: favorites.length ? (
                list(favorites)
              ) : (
                <Empty
                  image={Empty.PRESENTED_IMAGE_SIMPLE}
                  description="暂无收藏问题"
                />
              ),
            },
          ]}
        />
      }
    >
      <button className="quick-question-trigger" aria-label="打开快捷提问">
        <ThunderboltOutlined /> 快捷提问
      </button>
    </Popover>
  );
}
