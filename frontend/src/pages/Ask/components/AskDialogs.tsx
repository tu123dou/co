import { Alert, Drawer, Input, Modal, Table, Tabs, Tag, message } from "antd";
import { useState } from "react";
import { createFeedback } from "../../../api/feedback";
import type { Catalog } from "../../../api/workbench";
import styles from "../AskPage.module.scss";

export function CatalogDrawer({
  catalog,
  open,
  onClose,
}: {
  catalog: Catalog | null;
  open: boolean;
  onClose: () => void;
}) {
  return (
    <Drawer
      className={styles.catalogDrawer}
      title="数据与指标"
      open={open}
      onClose={onClose}
      width={600}
    >
      {catalog && (
        <>
          <Alert
            type="info"
            showIcon
            message="算力基础设施与服务 · 经营数据"
            description={`覆盖 ${catalog.dataset.start_date} 至 ${catalog.dataset.cutoff_date}，所有金额采用不含税管理口径。`}
          />
          <Tabs
            items={[
              {
                key: "metrics",
                label: "指标口径",
                children: (
                  <div className={styles["ask-catalog-metrics"]}>
                    {Object.entries(catalog.metrics).map(([key, metric]) => (
                      <div key={key}>
                        <h3>
                          {metric.name}
                          <Tag>{metric.unit}</Tag>
                        </h3>
                        <p>{metric.definition}</p>
                        <small>{key} · v1</small>
                      </div>
                    ))}
                  </div>
                ),
              },
              {
                key: "range",
                label: "数据范围",
                children: (
                  <>
                    <h3>经营单元</h3>
                    <div className={styles["ask-catalog-tags"]}>
                      {catalog.values.org_unit?.map((value) => (
                        <Tag key={value}>{value}</Tag>
                      ))}
                    </div>
                    <h3>产品线</h3>
                    <div className={styles["ask-catalog-tags"]}>
                      {catalog.values.product_line?.map((value) => (
                        <Tag key={value}>{value}</Tag>
                      ))}
                    </div>
                    <h3>数据记录</h3>
                    <Table
                      rowKey="table"
                      size="small"
                      pagination={false}
                      dataSource={catalog.data_tables}
                      columns={[
                        { title: "数据表", dataIndex: "table" },
                        { title: "数据表描述", dataIndex: "description" },
                        { title: "记录数", dataIndex: "count", align: "right" },
                      ]}
                      scroll={{ x: 620 }}
                    />
                  </>
                ),
              },
            ]}
          />
        </>
      )}
    </Drawer>
  );
}

export function FeedbackDialog({
  messageId,
  onClose,
}: {
  messageId: string | null;
  onClose: () => void;
}) {
  const [comment, setComment] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const close = () => {
    setComment("");
    onClose();
  };
  return (
    <Modal
      title="回答反馈"
      open={Boolean(messageId)}
      okText="提交反馈"
      cancelText="取消"
      confirmLoading={submitting}
      okButtonProps={{ disabled: !comment.trim() }}
      onCancel={close}
      onOk={async () => {
        if (!messageId) return;
        setSubmitting(true);
        try {
          await createFeedback(messageId, comment.trim());
          message.success("反馈已保存");
          close();
        } catch (cause) {
          message.error((cause as Error).message);
        } finally {
          setSubmitting(false);
        }
      }}
    >
      <p>请说明有疑问的数据或口径，帮助后续核查。</p>
      <Input.TextArea
        value={comment}
        onChange={(event) => setComment(event.target.value)}
        maxLength={1000}
        rows={4}
        placeholder="例如：收入统计范围与预期不一致…"
      />
    </Modal>
  );
}
