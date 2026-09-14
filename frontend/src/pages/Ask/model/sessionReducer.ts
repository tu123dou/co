import type { AnalysisStep } from "../../../models/ask";
import type { ChatMessage } from "../../../api/conversations";

export type GenerationStatus = "idle" | "creating" | "streaming" | "cancelling";

export type SessionState = {
  conversationId: string | null;
  messages: ChatMessage[];
  draft: string;
  loadingConversation: boolean;
  generation: GenerationStatus;
  stage: string;
  liveAnalysis: AnalysisStep[];
  error: string;
};

export const initialSessionState: SessionState = {
  conversationId: null,
  messages: [],
  draft: "",
  loadingConversation: false,
  generation: "idle",
  stage: "",
  liveAnalysis: [],
  error: "",
};

type Action =
  | { type: "conversation/loading"; id: string }
  | { type: "conversation/loaded"; id: string; messages: ChatMessage[] }
  | { type: "conversation/reset" }
  | { type: "conversation/failed"; message: string }
  | { type: "draft/changed"; value: string }
  | { type: "generation/creating" }
  | { type: "generation/started"; id: string; question: ChatMessage }
  | { type: "generation/stage"; stage: string }
  | { type: "generation/analysis"; step: AnalysisStep }
  | { type: "generation/result"; message: ChatMessage }
  | { type: "generation/cancelling" }
  | { type: "generation/cancelled"; message: ChatMessage }
  | { type: "generation/failed"; message: string; draft: string }
  | { type: "error/dismissed" };

export function sessionReducer(state: SessionState, action: Action): SessionState {
  switch (action.type) {
    case "conversation/loading":
      return {
        ...state,
        conversationId: action.id,
        messages: [],
        loadingConversation: true,
        error: "",
        liveAnalysis: [],
      };
    case "conversation/loaded":
      return {
        ...state,
        conversationId: action.id,
        messages: action.messages,
        loadingConversation: false,
        error: "",
      };
    case "conversation/reset":
      return { ...initialSessionState };
    case "conversation/failed":
      return { ...state, loadingConversation: false, error: action.message };
    case "draft/changed":
      return { ...state, draft: action.value };
    case "generation/creating":
      return {
        ...state,
        generation: "creating",
        draft: "",
        error: "",
        stage: "正在创建会话",
        liveAnalysis: [],
      };
    case "generation/started":
      return {
        ...state,
        conversationId: action.id,
        generation: "streaming",
        stage: "理解问题",
        messages: [...state.messages, action.question],
      };
    case "generation/stage":
      return { ...state, stage: action.stage };
    case "generation/analysis": {
      const index = state.liveAnalysis.findIndex((item) => item.key === action.step.key);
      const liveAnalysis =
        index < 0
          ? [...state.liveAnalysis, action.step]
          : state.liveAnalysis.map((item, itemIndex) => (itemIndex === index ? action.step : item));
      return { ...state, liveAnalysis };
    }
    case "generation/result":
      return {
        ...state,
        generation: "idle",
        stage: "",
        liveAnalysis: [],
        messages: [...state.messages, action.message],
      };
    case "generation/cancelling":
      return { ...state, generation: "cancelling", stage: "正在停止" };
    case "generation/cancelled":
      return {
        ...state,
        generation: "idle",
        stage: "",
        liveAnalysis: [],
        messages: [...state.messages, action.message],
      };
    case "generation/failed":
      return {
        ...state,
        generation: "idle",
        stage: "",
        liveAnalysis: [],
        error: action.message,
        draft: action.draft,
      };
    case "error/dismissed":
      return { ...state, error: "" };
  }
}
