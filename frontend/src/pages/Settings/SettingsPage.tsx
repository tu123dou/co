import { useEffect, useState } from "react";
import { Alert, Button, Input, InputNumber, Modal, Select, Spin, Switch, Tag, message } from "antd";
import {
  CheckOutlined,
  CommentOutlined,
  ControlOutlined,
  DeleteOutlined,
  FireOutlined,
  PlusOutlined,
  RobotOutlined,
  SettingOutlined,
  UnorderedListOutlined,
} from "@ant-design/icons";
import type { AskSettings } from "../../api/workbench";
import {
  getCatalog,
  getWorkbenchSettings,
  testModel,
  updateWorkbenchSettings,
} from "../../api/workbench";
import managementStyles from "../../styles/management.module.scss";
import styles from "./SettingsPage.module.scss";

type ModalName = "welcome" | "common" | "model" | "";

function SettingsPanel({
  settings,
  models,
  modelConfigured,
  testing,
  onTest,
  onSave,
}: {
  settings: AskSettings;
  models: string[];
  modelConfigured: boolean;
  testing: boolean;
  onTest: (model: string) => Promise<void>;
  onSave: (values: Partial<AskSettings>) => Promise<void>;
}) {
  const [modal, setModal] = useState<ModalName>(""),
    [saving, setSaving] = useState(false),
    [welcomeTitle, setWelcomeTitle] = useState(settings.welcome_title),
    [welcomeMessage, setWelcomeMessage] = useState(settings.welcome_message),
    [starterQuestions, setStarterQuestions] = useState<string[]>(settings.starter_questions),
    [threshold, setThreshold] = useState(settings.common_question_threshold),
    [model, setModel] = useState(settings.llm_model);

  useEffect(() => {
    setWelcomeTitle(settings.welcome_title);
    setWelcomeMessage(settings.welcome_message);
    setStarterQuestions(settings.starter_questions);
    setThreshold(settings.common_question_threshold);
    setModel(settings.llm_model);
  }, [settings]);

  const save = async (values: Partial<AskSettings>) => {
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

  const toggle = async (field: keyof AskSettings, checked: boolean) => {
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
    <div className={styles.settings}>
      <div className={styles.settingsGrid}>
        <div className={styles.settingCard}>
          <span className={`${styles.settingIcon} ${styles.blue}`}>
            <CommentOutlined />
          </span>
          <div className={styles.settingContent}>
            <h3>对话开场白</h3>
            <p>配置新对话的欢迎文案和开场问题</p>
          </div>
          <div className={styles.settingActions}>
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
        </div>
        <div className={styles.settingCard}>
          <span className={`${styles.settingIcon} ${styles.amber}`}>
            <UnorderedListOutlined />
          </span>
          <div className={styles.settingContent}>
            <h3>下一步问题建议</h3>
            <p>在回答下方展示相关延伸问题</p>
          </div>
          <div className={styles.settingActions}>
            <Switch
              checked={settings.suggestions_enabled}
              onChange={(checked) => toggle("suggestions_enabled", checked)}
            />
          </div>
        </div>
        <div className={styles.settingCard}>
          <span className={`${styles.settingIcon} ${styles.violet}`}>
            <RobotOutlined />
          </span>
          <div className={styles.settingContent}>
            <h3>模型配置</h3>
            <p>{settings.llm_model}</p>
          </div>
          <div className={styles.settingActions}>
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
        </div>
        <div className={styles.settingCard}>
          <span className={`${styles.settingIcon} ${styles.orange}`}>
            <FireOutlined />
          </span>
          <div className={styles.settingContent}>
            <h3>常见问题</h3>
            <p>成功提问满 {settings.common_question_threshold} 次后展示</p>
          </div>
          <div className={styles.settingActions}>
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
        <div className={styles.settingsForm}>
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
          <div className={styles.settingsFormHeading}>
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
            <div className={styles.starterQuestionRow} key={index}>
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
        <div className={`${styles.settingsForm} ${styles.thresholdForm}`}>
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
        <div className={styles.settingsForm}>
          <label>问数模型</label>
          <Select
            value={model}
            onChange={setModel}
            options={models.map((name) => ({ value: name, label: name }))}
            style={{ width: "100%" }}
          />
          <p>该模型用于理解自然语言并生成受控查询计划。</p>
          <p>向量模型由服务端配置，与这里选择的问数模型独立。</p>
          <Button icon={<CheckOutlined />} loading={testing} onClick={() => onTest(model)}>
            测试所选模型连接
          </Button>
        </div>
      </Modal>
    </div>
  );
}

/** 应用配置是与智能问数同级的独立路由页面。 */
export default function SettingsPage() {
  const [settings, setSettings] = useState<AskSettings | null>(null);
  const [models, setModels] = useState<string[]>([]);
  const [modelConfigured, setModelConfigured] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [loadVersion, setLoadVersion] = useState(0);
  const [testing, setTesting] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setLoadError("");
    Promise.all([getWorkbenchSettings(controller.signal), getCatalog(controller.signal)])
      .then(([currentSettings, catalog]) => {
        if (controller.signal.aborted) return;
        setSettings(currentSettings);
        setModels(catalog?.model?.available || []);
        setModelConfigured(Boolean(catalog?.model?.configured));
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          setSettings(null);
          setLoadError(error instanceof Error ? error.message : "无法获取应用配置，请重试");
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [loadVersion]);

  return (
    <div className={managementStyles.page}>
      <section className={`${managementStyles.card} ${styles.settingsPage}`}>
        <div className={managementStyles.heading}>
          <ControlOutlined />
          <strong>应用配置</strong>
          <span>以下设置仅对当前用户生效</span>
        </div>
        {loading ? (
          <div className={managementStyles.loading}>
            <Spin size="large" />
          </div>
        ) : loadError ? (
          <Alert
            type="error"
            showIcon
            message="应用配置加载失败"
            description={loadError}
            action={
              <Button onClick={() => setLoadVersion((version) => version + 1)}>重新加载</Button>
            }
          />
        ) : (
          settings && (
            <SettingsPanel
              settings={settings}
              models={models}
              modelConfigured={modelConfigured}
              testing={testing}
              onSave={async (values) => setSettings(await updateWorkbenchSettings(values))}
              onTest={async (model) => {
                setTesting(true);
                try {
                  const result = await testModel(model);
                  message.success(
                    `${result.model} 连接成功，耗时 ${(result.duration_ms / 1000).toFixed(1)} 秒`,
                  );
                } catch (error) {
                  message.error((error as Error).message);
                } finally {
                  setTesting(false);
                }
              }}
            />
          )
        )}
      </section>
    </div>
  );
}
