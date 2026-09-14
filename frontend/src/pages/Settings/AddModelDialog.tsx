import { useEffect, useRef, useState } from "react";
import { Alert, Button, Form, Input, Modal, Select, Switch, message as antdMessage } from "antd";
import {
  ApiOutlined,
  PlusCircleFilled,
  EyeOutlined,
  EyeInvisibleOutlined,
} from "@ant-design/icons";
import {
  addCustomModel,
  testCustomModel,
  editCustomModel,
  testEditedModel,
} from "../../api/workbench";
import type { CustomModel, CustomModelInput } from "../../api/workbench";
import styles from "./SettingsPage.module.scss";

export default function AddModelDialog({
  onClose,
  onAdded,
  model,
}: {
  onClose: () => void;
  onAdded: (model: CustomModel) => void;
  model?: CustomModel;
}) {
  const [form] = Form.useForm<CustomModelInput>();
  const apiFormat = Form.useWatch("api_format", form);
  const fullUrl = Form.useWatch("full_url", form);
  const [message, contextHolder] = antdMessage.useMessage();
  const [keyVisible, setKeyVisible] = useState(false);
  const [action, setAction] = useState<"test" | "add" | null>(null);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);

  async function submit(mode: "test" | "add") {
    if (controller.current) return;
    let values: CustomModelInput;
    try {
      values = await form.validateFields();
    } catch {
      return;
    }
    if (controller.current) return;
    const request = new AbortController();
    controller.current = request;
    setAction(mode);
    try {
      const body = {
        full_url: values.full_url,
        request_url: values.request_url.trim(),
        api_format: values.api_format,
        display_name: values.display_name?.trim() ?? "",
        api_key: values.api_key?.trim() ?? "",
        model_name: values.model_name.trim(),
      };
      if (mode === "test") {
        const result = model
          ? await testEditedModel(
              model.id,
              { ...body, api_key: body.api_key || undefined },
              request.signal,
            )
          : await testCustomModel(body, request.signal);
        if (!request.signal.aborted) {
          message.success(`连接成功，耗时 ${(result.duration_ms / 1000).toFixed(1)} 秒`);
        }
      } else {
        const saved = model
          ? await editCustomModel(
              model.id,
              { ...body, api_key: body.api_key || undefined },
              request.signal,
            )
          : await addCustomModel(body, request.signal);
        if (!request.signal.aborted) {
          form.resetFields();
          onAdded(saved);
        }
      }
    } catch (error) {
      if (!request.signal.aborted) {
        message.error(error instanceof Error ? error.message : "操作失败，请重试");
      }
    } finally {
      if (!request.signal.aborted) setAction(null);
      controller.current = null;
    }
  }

  return (
    <Modal
      open
      centered
      title={
        <>
          <PlusCircleFilled /> {model ? "编辑模型" : "新增模型"}
        </>
      }
      width={560}
      onCancel={onClose}
      closable={action !== "add"}
      maskClosable={!action}
      keyboard={!action}
      className={styles.addModelDialog}
      footer={
        <div className={styles.modelDialogFooter}>
          <Button
            icon={<ApiOutlined />}
            loading={action === "test"}
            disabled={action === "add"}
            onClick={() => void submit("test")}
          >
            测试连接
          </Button>
          <div>
            <Button type="text" disabled={action === "add"} onClick={onClose}>
              取消
            </Button>
            <Button
              type="primary"
              loading={action === "add"}
              disabled={action === "test"}
              onClick={() => void submit("add")}
            >
              {model ? "保存" : "添加"}
            </Button>
          </div>
        </div>
      }
    >
      {contextHolder}
      <Form
        component="div"
        form={form}
        layout="vertical"
        disabled={action !== null}
        requiredMark
        autoComplete="off"
        initialValues={
          model
            ? { ...model, full_url: model.full_url ?? true, api_key: "" }
            : { api_format: "openai", display_name: "", full_url: false }
        }
      >
        <Form.Item label="API 格式" name="api_format" rules={[{ required: true }]}>
          <Select
            options={[
              { value: "openai", label: "OpenAI Chat Completions 格式" },
              { value: "anthropic", label: "Anthropic Messages 格式" },
            ]}
          />
        </Form.Item>
        <div className={styles.urlModeRow}>
          <span>地址模式</span>
          <Form.Item name="full_url" valuePropName="checked" noStyle>
            <Switch aria-label="完整 URL" checkedChildren="完整 URL" unCheckedChildren="基础 URL" />
          </Form.Item>
        </div>
        <Form.Item
          label="自定义请求地址"
          name="request_url"
          extra={
            fullUrl
              ? "直接使用完整请求 URL，不拼接路径。"
              : apiFormat === "anthropic"
                ? "自动补充 /v1/messages；地址已以 /v1 结尾时仅补充 /messages。"
                : "自动在基础地址末尾补充 /chat/completions。"
          }
          validateFirst
          rules={[
            { required: true, whitespace: true, message: "请输入请求地址" },
            { max: 1000, message: "地址不能超过 1000 个字符" },
            {
              validator: (_, value: unknown) => {
                try {
                  if (typeof value !== "string") throw new Error();
                  const url = new URL(value.trim());
                  if (
                    url.protocol !== "https:" ||
                    url.username ||
                    url.password ||
                    url.search ||
                    url.hash ||
                    (fullUrl && url.pathname === "/")
                  )
                    throw new Error();
                  return Promise.resolve();
                } catch {
                  return Promise.reject(new Error("请输入不含账号或查询参数的 HTTPS 地址"));
                }
              },
            },
          ]}
        >
          <Input
            placeholder={
              !fullUrl
                ? apiFormat === "anthropic"
                  ? "例如 https://api.anthropic.com"
                  : "例如 https://api.openai.com/v1"
                : apiFormat === "anthropic"
                  ? "例如 https://api.anthropic.com/v1/messages"
                  : "例如 https://api.openai.com/v1/chat/completions"
            }
            maxLength={1000}
          />
        </Form.Item>
        <Form.Item
          label="模型 ID"
          name="model_name"
          rules={[{ required: true, whitespace: true, message: "请输入模型 ID" }, { max: 100 }]}
        >
          <Input placeholder="输入模型 ID" maxLength={100} />
        </Form.Item>
        <Form.Item
          label="模型展示名称"
          name="display_name"
          extra="在模型列表中展示的名称，未设置时默认显示模型 ID。"
          rules={[{ max: 100 }]}
        >
          <Input placeholder="请输入模型展示名称" maxLength={100} />
        </Form.Item>
        <Form.Item
          label="API 密钥"
          name="api_key"
          rules={[{ required: !model, whitespace: true, message: "请输入 API Key" }, { max: 4096 }]}
          extra={
            model
              ? "留空保留已保存的密钥；测试修改后的地址时也会使用该密钥，请确认目标可信。"
              : undefined
          }
        >
          <Input
            type="text"
            className={!keyVisible ? styles.maskedKey : undefined}
            placeholder={model ? "留空保留已有密钥" : "请输入 API Key"}
            autoComplete="off"
            spellCheck={false}
            data-lpignore="true"
            data-1p-ignore="true"
            suffix={
              <Button
                type="text"
                size="small"
                aria-label={keyVisible ? "隐藏密钥" : "显示密钥"}
                icon={keyVisible ? <EyeInvisibleOutlined /> : <EyeOutlined />}
                onClick={() => setKeyVisible((visible) => !visible)}
              />
            }
            maxLength={4096}
          />
        </Form.Item>
      </Form>
      <p className={styles.modelSecurityNote}>密钥加密保存；测试连接会调用模型并可能产生费用。</p>
      {window.location.protocol === "http:" &&
        !["localhost", "127.0.0.1", "[::1]"].includes(window.location.hostname) && (
          <Alert
            type="warning"
            showIcon
            message="当前页面使用 HTTP，提交密钥前请切换到 HTTPS 或安全的本地连接。"
          />
        )}
    </Modal>
  );
}
