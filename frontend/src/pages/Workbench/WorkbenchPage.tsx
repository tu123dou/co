import { useState } from "react";
import ConversationView from "./components/ConversationView";
import ConversationComposer from "./components/ConversationComposer/ConversationComposer";
import DataCatalogDrawer from "./components/DataCatalogDrawer/DataCatalogDrawer";
import FeedbackModal from "./components/FeedbackModal/FeedbackModal";
import useWorkbenchController from "./hooks/useWorkbenchController";
import { WorkbenchProvider } from "./WorkbenchContext";

/** 智能问数页面：组合会话信息、内容状态、输入区和页面级辅助弹层。 */
export default function WorkbenchPage() {
  const session = useWorkbenchController();
  const [drawer, setDrawer] = useState("");
  const [feedback, setFeedback] = useState("");
  const [remark, setRemark] = useState("");

  return <WorkbenchProvider value={{ session, openCatalog: () => setDrawer("catalog"), openFeedback: setFeedback }}>
    <ConversationView />
    <ConversationComposer />
    <DataCatalogDrawer open={drawer === "catalog"} catalog={session.catalog} onClose={() => setDrawer("")} />
    <FeedbackModal messageId={feedback} remark={remark} setRemark={setRemark} onClose={() => setFeedback("")} />
  </WorkbenchProvider>;
}
