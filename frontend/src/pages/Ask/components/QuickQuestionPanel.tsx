import { Button, Empty, Popconfirm, Popover, Tabs, Tag } from "antd";
import { DeleteOutlined, StarFilled, ThunderboltOutlined } from "@ant-design/icons";
import type { CommonQuestion, FavoriteQuestion } from "../../../api/questions";
import styles from "../AskPage.module.scss";

export default function QuickQuestionPanel({
  open,
  onOpenChange,
  common,
  favorites,
  commonEnabled,
  onChoose,
  onRemoveCommon,
  onRemoveFavorite,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  common: CommonQuestion[];
  favorites: FavoriteQuestion[];
  commonEnabled: boolean;
  onChoose: (question: string) => void;
  onRemoveCommon: (id: number) => Promise<void>;
  onRemoveFavorite: (id: number) => Promise<void>;
}) {
  const renderList = (
    rows: Array<{ id: number; question: string; success_count?: number }>,
    remove: (id: number) => Promise<void>,
    confirmation: string,
  ) =>
    rows.length ? (
      <div className={styles["ask-quick-list"]}>
        {rows.map((row) => (
          <div key={row.id}>
            <button onClick={() => onChoose(row.question)}>
              <span>{row.question}</span>
              {row.success_count !== undefined && <Tag>{row.success_count} 次</Tag>}
            </button>
            <Popconfirm title={confirmation} onConfirm={() => remove(row.id)}>
              <Button
                type="text"
                size="small"
                icon={row.success_count === undefined ? <StarFilled /> : <DeleteOutlined />}
                aria-label={confirmation}
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
        <span className={styles["ask-quick-title"]}>
          <ThunderboltOutlined /> 快捷提问
        </span>
      }
      content={
        <Tabs
          className={styles["ask-quick-tabs"]}
          items={[
            {
              key: "common",
              label: "常见",
              children: renderList(common, onRemoveCommon, "删除这个常见问题？"),
            },
            {
              key: "favorites",
              label: (
                <span>
                  <StarFilled /> 收藏
                </span>
              ),
              children: renderList(favorites, onRemoveFavorite, "取消收藏这个问题？"),
            },
          ]}
        />
      }
    >
      <button className={styles["ask-quick-trigger"]} aria-label="打开快捷提问">
        <ThunderboltOutlined /> 快捷提问
      </button>
    </Popover>
  );
}
