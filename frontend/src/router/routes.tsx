import { Navigate, type RouteObject } from "react-router-dom";
import type { CurrentUser } from "../api/auth";
import WorkspaceLayout from "../layouts/WorkspaceLayout/WorkspaceLayout";
import FeedbackPage from "../pages/Feedback/FeedbackPage";
import SettingsPage from "../pages/Settings/SettingsPage";
import AskPage from "../pages/Ask/AskPage";
import { ROUTES } from "./paths";

/** 三个业务页面作为同级子路由，共用传统管理后台布局。 */
export function createAppRoutes(user: CurrentUser, onLogout: () => void): RouteObject[] {
  return [
    {
      path: "/",
      element: <WorkspaceLayout user={user} onLogout={onLogout} />,
      children: [
        { index: true, element: <Navigate to={ROUTES.ask} replace /> },
        { path: ROUTES.ask, element: <AskPage /> },
        { path: ROUTES.settings, element: <SettingsPage /> },
        {
          path: ROUTES.feedback,
          element: <FeedbackPage isSuperuser={Boolean(user.is_superuser)} />,
        },
      ],
    },
    { path: "*", element: <Navigate to={ROUTES.ask} replace /> },
  ];
}
