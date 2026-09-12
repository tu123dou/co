export type WorkbenchSettings = {
  welcome_enabled: boolean;
  welcome_title: string;
  welcome_message: string;
  starter_questions: string[];
  suggestions_enabled: boolean;
  common_questions_enabled: boolean;
  common_question_threshold: number;
  llm_model: string;
  updated_at?: string;
};

export type CommonQuestion = {
  id: number;
  question: string;
  success_count: number;
  last_asked_at: string;
};

export const DEFAULT_WORKBENCH_SETTINGS: WorkbenchSettings = {
  welcome_enabled: true,
  welcome_title: "你好，今天想了解哪些数据？",
  welcome_message: "从收入趋势到目标达成，用自然语言探索你的经营数据。",
  starter_questions: [
    "今年各经营单元确认收入排名",
    "今年各产品线的收入占比",
    "华东区今年按月收入趋势，与去年同期相比",
    "2026年8月各产品线毛利率",
    "今年各区域收入目标达成率",
    "2026年8月回款额比上个月变化多少",
  ],
  suggestions_enabled: true,
  common_questions_enabled: true,
  common_question_threshold: 3,
  llm_model: "qwen3.8-max",
};
