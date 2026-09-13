import { createContext, useContext, type ReactNode } from "react";
import type useWorkbenchController from "./hooks/useWorkbenchController";

type WorkbenchContextValue = {
  session: ReturnType<typeof useWorkbenchController>;
  openCatalog: () => void;
  openFeedback: (messageId: string) => void;
};

const WorkbenchContext = createContext<WorkbenchContextValue | null>(null);

export function WorkbenchProvider({ value, children }: { value: WorkbenchContextValue; children: ReactNode }) {
  return <WorkbenchContext.Provider value={value}>{children}</WorkbenchContext.Provider>;
}

export function useWorkbench() {
  const context = useContext(WorkbenchContext);
  if (!context) throw new Error("useWorkbench 必须在 WorkbenchProvider 内使用");
  return context;
}
