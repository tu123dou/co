import { useEffect, useState } from "react";
import {
  Alert,
  Button,
  Input,
  InputNumber,
  Modal,
  Select,
  Switch,
  Tag,
  message,
} from "antd";
import {
  CheckOutlined,
  CommentOutlined,
  DeleteOutlined,
  FireOutlined,
  PlusOutlined,
  RobotOutlined,
  SettingOutlined,
  UnorderedListOutlined,
} from "@ant-design/icons";
import type { WorkbenchSettings } from "./workbenchConfig";

type ModalName = "welcome" | "common" | "model" | "";

export default function WorkbenchSettingsPanel({
  settings,
  models,
  modelConfigured,
  testing,
  onTest,
  onSave,
}: {
  settings: WorkbenchSettings;
  models: string[];
  modelConfigured: boolean;
  testing: boolean;
  onTest: (model: string) => Promise<void>;
  onSave: (values: Partial<WorkbenchSettings>) => Promise<void>;
}) {
  const [modal, setModal] = useState<ModalName>(""),
    [saving, setSaving] = useState(false),
    [welcomeTitle, setWelcomeTitle] = useState(settings.welcome_title),
    [welcomeMessage, setWelcomeMessage] = useState(settings.welcome_message),
    [starterQuestions, setStarterQuestions] = useState<string[]>(
      settings.starter_questions,
    ),
    [threshold, setThreshold] = useState(settings.common_question_threshold),
    [model, setModel] = useState(settings.llm_model);

  useEffect(() => {
    setWelcomeTitle(settings.welcome_title);
    setWelcomeMessage(settings.welcome_message);
    setStarterQuestions(settings.starter_questions);
    setThreshold(settings.common_question_threshold);
    setModel(settings.llm_model);
  }, [settings]);

  const save = async (values: Partial<WorkbenchSettings>) => {
    setSaving(true);
    try {
      await onSave(values);
      setModal("");
      message.success("设置已保存，仅对当前用户生效");
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const toggle = async (field: keyof WorkbenchSettings, checked: boolean) => {
    try {
      await onSave({ [field]: checked });
    } catch (error) {
      message.error((error as Error).message);
    }
  };

  const openModal = (name: ModalName) => {
    // 每次打开都以已保存配置为准，取消编辑后不会残留未保存草稿。
    setWelcomeTitle(settings.welcome_title);
    setWelcomeMessage(settings.welcome_message);
    setStarterQuestions(settings.starter_questions);
    setThreshold(settings.common_question_threshold);
    setModel(settings.llm_model);
    setModal(name);
  };

  return (
    <div className="settings">
      {/* <Alert
        type="info"
        showIcon
        message="以下设置仅对当前登录用户生效，不会影响其他用户。"
      /> */}
      <div className="settings-grid">
        <div className="setting-card">
          <span className="setting-icon blue"><CommentOutlined /></span>
          <div>
            <h3>对话开场白</h3>
            <p>配置新对话的欢迎文案和开场问题</p>
          </div>
          <Button
            type="text"
            icon={<SettingOutlined />}
            onClick={() => openModal("welcome")}
            aria-label="配置对话开场白"
          />
          <Switch
            checked={settings.welcome_enabled}
            onChange={(checked) => toggle("welcome_enabled", checked)}
          />
        </div>
        <div className="setting-card">
          <span className="setting-icon amber"><UnorderedListOutlined /></span>
          <div>
            <h3>下一步问题建议</h3>
            <p>在回答下方展示相关延伸问题</p>
          </div>
          <Switch
            checked={settings.suggestions_enabled}
            onChange={(checked) => toggle("suggestions_enabled", checked)}
          />
        </div>
        <div className="setting-card">
          <span className="setting-icon violet"><RobotOutlined /></span>
          <div>
            <h3>模型配置</h3>
            <p>{settings.llm_model}</p>
          </div>
          <Button
            type="text"
            icon={<SettingOutlined />}
            onClick={() => openModal("model")}
            aria-label="配置模型"
          />
          <Tag color={modelConfigured ? "green" : "orange"}>
            {modelConfigured ? "已连接" : "未配置"}
          </Tag>
        </div>
        <div className="setting-card">
          <span className="setting-icon orange"><FireOutlined /></span>
          <div>
            <h3>常见问题</h3>
            <p>成功提问满 {settings.common_question_threshold} 次后展示</p>
          </div>
          <Button
            type="text"
            icon={<SettingOutlined />}
            onClick={() => openModal("common")}
            aria-label="配置常见问题"
          />
          <Switch
            checked={settings.common_questions_enabled}
            onChange={(checked) => toggle("common_questions_enabled", checked)}
          />
        </div>
      </div>

      <hr />
      <h3>关于工作台</h3>
      <p>经管之星 v0.1 · 本地部署</p>
      <p>PostgreSQL 业务数据 · 只读问数查询</p>

      <Modal
        title="对话开场白"
        open={modal === "welcome"}
        onCancel={() => setModal("")}
        onOk={() =>
          save({
            welcome_title: welcomeTitle,
            welcome_message: welcomeMessage,
            starter_questions: starterQuestions.filter((item) => item.trim()),
          })
        }
        okText="保存"
        cancelText="取消"
        confirmLoading={saving}
        okButtonProps={{ disabled: !welcomeTitle.trim() || !welcomeMessage.trim() }}
        width={680}
      >
        <div className="settings-form">
          <label>开场标题</label>
          <Input
            value={welcomeTitle}
            onChange={(event) => setWelcomeTitle(event.target.value)}
            maxLength={100}
            showCount
          />
          <label>开场说明</label>
          <Input.TextArea
            value={welcomeMessage}
            onChange={(event) => setWelcomeMessage(event.target.value)}
            maxLength={500}
            showCount
            rows={3}
          />
          <div className="settings-form-heading">
            <label>开场问题 · {starterQuestions.length}/10</label>
            <Button
              type="link"
              icon={<PlusOutlined />}
              disabled={starterQuestions.length >= 10}
              onClick={() => setStarterQuestions((items) => [...items, ""])}
            >
              添加问题
            </Button>
          </div>
          {starterQuestions.map((question, index) => (
            <div className="starter-question-row" key={index}>
              <Input
                value={question}
                maxLength={1000}
                placeholder="请输入开场问题"
                onChange={(event) =>
                  setStarterQuestions((items) =>
                    items.map((item, itemIndex) =>
                      itemIndex === index ? event.target.value : item,
                    ),
                  )
                }
              />
              <Button
                type="text"
                danger
                icon={<DeleteOutlined />}
                aria-label="删除开场问题"
                onClick={() =>
                  setStarterQuestions((items) =>
                    items.filter((_, itemIndex) => itemIndex !== index),
                  )
                }
              />
            </div>
          ))}
        </div>
      </Modal>

      <Modal
        title="常见问题设置"
        open={modal === "common"}
        onCancel={() => setModal("")}
        onOk={() => save({ common_question_threshold: threshold })}
        okText="保存"
        cancelText="取消"
        confirmLoading={saving}
      >
        <div className="settings-form threshold-form">
          <label>问题频次阈值</label>
          <div>
            <InputNumber
              min={1}
              max={100}
              value={threshold}
              onChange={(value) => setThreshold(value || 1)}
            />
            <span>次</span>
          </div>
          <p>同一问题成功完成查询达到该次数后，会出现在你自己的常见问题中。</p>
        </div>
      </Modal>

      <Modal
        title="模型配置"
        open={modal === "model"}
        onCancel={() => setModal("")}
        onOk={() => save({ llm_model: model })}
        okText="保存"
        cancelText="取消"
        confirmLoading={saving}
      >
        <div className="settings-form">
          <label>问数模型</label>
          <Select
            value={model}
            onChange={setModel}
            options={models.map((name) => ({ value: name, label: name }))}
            style={{ width: "100%" }}
          />
          <p>该模型用于理解自然语言并生成受控查询计划。</p>
          <p>向量模型固定为 qwen3.7-text-embedding-flash。</p>
          <Button
            icon={<CheckOutlined />}
            loading={testing}
            onClick={() => onTest(model)}
          >
            测试所选模型连接
          </Button>
        </div>
      </Modal>
    </div>
  );
}
