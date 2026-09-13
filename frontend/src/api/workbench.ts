import { post, request } from "./client";
import type { WorkbenchSettings } from "../config/workbench";
import type { WorkbenchCatalog } from "../models/workbench";

export const getCatalog = () => request<WorkbenchCatalog>("/catalog");
export const getWorkbenchSettings = () => request<WorkbenchSettings>("/workbench/settings");
export const updateWorkbenchSettings = (body: Partial<WorkbenchSettings>) =>
  request<WorkbenchSettings>("/workbench/settings", { method: "PATCH", body: JSON.stringify(body) });
export const testModel = (model: string) => post<any>("/model/test", { model });
