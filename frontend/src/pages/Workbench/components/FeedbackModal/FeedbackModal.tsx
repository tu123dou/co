import { Input, Modal, message } from "antd";
import { createFeedback } from "../../../../api/feedback";

/** 针对单条 AI 回答提交问题说明。 */
export default function FeedbackModal({ messageId, remark, setRemark, onClose }: {
  messageId: string; remark: string; setRemark: (value: string) => void; onClose: () => void;
}) {
  return <Modal title="回答反馈" open={Boolean(messageId)} okText="提交反馈" cancelText="取消"
    okButtonProps={{ disabled: !remark.trim() }}
    onCancel={() => { setRemark(""); onClose(); }}
    onOk={async () => {
      try {
        await createFeedback(messageId, remark);
        message.success("反馈已保存");
        setRemark("");
        onClose();
      } catch (error) { message.error((error as Error).message); }
    }}>
    <p>请说明有疑问的数据或口径，帮助后续核查。</p>
    <Input.TextArea value={remark} onChange={(event) => setRemark(event.target.value)}
      maxLength={1000} rows={4} placeholder="例如：收入统计范围与预期不一致…" />
  </Modal>;
}
