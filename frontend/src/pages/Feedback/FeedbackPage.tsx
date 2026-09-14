import { useEffect, useState } from "react";
import {
  Button,
  Empty,
  Input,
  Modal,
  Pagination,
  Select,
  Table,
  Tag,
  message as antdMessage,
} from "antd";
import { ExclamationCircleFilled, SearchOutlined } from "@ant-design/icons";
import { listFeedbacks, reviewFeedback, type FeedbackRecord } from "../../api/feedback";
import managementStyles from "../../styles/management.module.scss";
import styles from "./FeedbackPage.module.scss";

const formatTime = (value: string) =>
  new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  })
    .format(new Date(value))
    .replaceAll("/", "-");

export default function FeedbackManagement({ isSuperuser }: { isSuperuser: boolean }) {
  const [message, contextHolder] = antdMessage.useMessage();
  const [rows, setRows] = useState<FeedbackRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [query, setQuery] = useState({
    page: 1,
    pageSize: 10,
    question: "",
    username: "",
    status: "",
  });
  const { page, pageSize, status } = query;
  const [question, setQuestion] = useState("");
  const [username, setUsername] = useState("");
  const [loading, setLoading] = useState(false);
  const [current, setCurrent] = useState<FeedbackRecord | null>(null);
  const [reviewStatus, setReviewStatus] = useState<"pending" | "resolved">("pending");
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    const params = new URLSearchParams({
      question: query.question,
      username: query.username,
      status: query.status,
      page: String(query.page),
      page_size: String(query.pageSize),
    });
    listFeedbacks(params, controller.signal)
      .then((data) => {
        if (controller.signal.aborted) return;
        setRows(data.items);
        setTotal(data.total);
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted)
          message.error(error instanceof Error ? error.message : "反馈加载失败");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [query]);

  const search = () => setQuery((previous) => ({ ...previous, page: 1, question, username }));

  const openReview = (row: FeedbackRecord) => {
    setCurrent(row);
    setReviewStatus(row.status);
    setNote(row.resolution_note || "");
  };

  return (
    <div className={managementStyles.page}>
      {contextHolder}
      <section className={managementStyles.card}>
        <div className={managementStyles.heading}>
          <ExclamationCircleFilled />
          <strong>回复校对</strong>
          <span>查看用户标注为数据或口径有误的 AI 回答</span>
        </div>
        <div className={styles.filters}>
          <Input
            prefix={<SearchOutlined />}
            placeholder="搜索问题…"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            onPressEnter={search}
            allowClear
          />
          <Input
            placeholder="搜索用户…"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            onPressEnter={search}
            allowClear
          />
          <Select
            value={status}
            onChange={(value) => setQuery((previous) => ({ ...previous, page: 1, status: value }))}
            options={[
              { value: "", label: "全部状态" },
              { value: "pending", label: "待处理" },
              { value: "resolved", label: "已处理" },
            ]}
          />
          <Button type="primary" onClick={search}>
            查询
          </Button>
          <span className={styles.total}>共 {total} 条</span>
        </div>
        <Table<FeedbackRecord>
          rowKey="id"
          loading={loading}
          pagination={false}
          dataSource={rows}
          locale={{ emptyText: <Empty description="暂无反馈记录" /> }}
          columns={[
            {
              title: "序号",
              width: 80,
              align: "center",
              render: (_, __, index) => (page - 1) * pageSize + index + 1,
            },
            { title: "用户", dataIndex: "display_name", width: 140 },
            { title: "问题", dataIndex: "question", ellipsis: true },
            {
              title: "反馈内容",
              dataIndex: "comment",
              ellipsis: true,
              render: (value: string) => value || "—",
            },
            { title: "反馈时间", dataIndex: "created_at", width: 195, render: formatTime },
            {
              title: "状态",
              dataIndex: "status",
              width: 120,
              render: (value) =>
                value === "resolved" ? (
                  <Tag color="green">已处理</Tag>
                ) : (
                  <Tag color="orange">待处理</Tag>
                ),
            },
            {
              title: "操作",
              width: 100,
              render: (_, row) => (
                <Button
                  type="link"
                  onClick={() => {
                    if (!isSuperuser && row.status === "pending") {
                      message.warning("仅超管可以处理反馈");
                      return;
                    }
                    openReview(row);
                  }}
                >
                  {row.status === "pending" ? "处理" : "查看"}
                </Button>
              ),
            },
          ]}
          scroll={{ x: 1100 }}
        />
        <div className={styles.pagination}>
          <Pagination
            current={page}
            pageSize={pageSize}
            total={total}
            showSizeChanger
            showTotal={(value) => `共 ${value} 条`}
            onChange={(nextPage, nextSize) =>
              setQuery((previous) => ({
                ...previous,
                page: nextSize === previous.pageSize ? nextPage : 1,
                pageSize: nextSize,
              }))
            }
          />
        </div>
      </section>
      <Modal
        title="回复校对"
        open={Boolean(current)}
        confirmLoading={saving}
        okText="保存"
        cancelText={isSuperuser ? "取消" : "关闭"}
        footer={isSuperuser ? undefined : (_, { CancelBtn }) => <CancelBtn />}
        onCancel={() => setCurrent(null)}
        onOk={async () => {
          if (!current) return;
          setSaving(true);
          try {
            await reviewFeedback(current.id, { status: reviewStatus, resolution_note: note });
            message.success("处理结果已保存");
            setCurrent(null);
            setQuery((previous) => ({ ...previous }));
          } catch (error) {
            message.error((error as Error).message);
          } finally {
            setSaving(false);
          }
        }}
        width={720}
      >
        {current && (
          <div className={styles.reviewDetail}>
            <label>用户问题</label>
            <div>{current.question || "—"}</div>
            <label>AI 回答</label>
            <div className={styles.reviewAnswer}>{current.answer}</div>
            <label>用户反馈</label>
            <div>{current.comment}</div>
            <label>处理状态</label>
            <Select
              disabled={!isSuperuser}
              value={reviewStatus}
              onChange={setReviewStatus}
              options={[
                { value: "pending", label: "待处理" },
                { value: "resolved", label: "已处理" },
              ]}
            />
            <label>处理说明</label>
            <Input.TextArea
              disabled={!isSuperuser}
              rows={4}
              maxLength={2000}
              showCount
              value={note}
              onChange={(event) => setNote(event.target.value)}
              placeholder="填写核查结论或后续处理说明"
            />
          </div>
        )}
      </Modal>
    </div>
  );
}
