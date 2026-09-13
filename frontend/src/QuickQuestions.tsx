import { Button, Empty, Popconfirm, Popover, Tabs, Tag } from "antd";
import { DeleteOutlined, StarFilled, ThunderboltOutlined } from "@ant-design/icons";
import type { CommonQuestion } from "./workbenchConfig";

export default function QuickQuestions({
  open,
  onOpenChange,
  common,
  favorites,
  commonEnabled,
  onPick,
  onRemoveCommon,
  onRemoveFavorite,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  common: CommonQuestion[];
  favorites: any[];
  commonEnabled: boolean;
  onPick: (question: string) => void;
  onRemoveCommon: (id: number) => Promise<void>;
  onRemoveFavorite: (id: number) => Promise<void>;
}) {
  const list = (
    rows: Array<{ id: number; question: string; success_count?: number }>,
    remove: (id: number) => Promise<void>,
    removeTitle: string,
  ) =>
    rows.length ? (
      <div className="quick-question-list">
        {rows.map((row) => (
          <div className="quick-question-row" key={row.id}>
            <button onClick={() => onPick(row.question)}>
              <span>{row.question}</span>
              {row.success_count != null && <Tag>{row.success_count} 次</Tag>}
            </button>
            <Popconfirm title={removeTitle} onConfirm={() => remove(row.id)}>
              <Button
                type="text"
                size="small"
                icon={row.success_count == null ? <StarFilled /> : <DeleteOutlined />}
                aria-label={removeTitle}
              />
            </Popconfirm>
          </div>
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
              children: list(common, onRemoveCommon, "删除这个常见问题？"),
            },
            {
              key: "favorites",
              label: (
                <span>
                  <StarFilled /> 收藏
                </span>
              ),
              children: favorites.length ? (
                list(favorites, onRemoveFavorite, "取消收藏这个问题？")
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
