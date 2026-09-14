import { useEffect, useState } from "react";
import { Spin } from "antd";
import { useLocation, useRoutes } from "react-router-dom";
import { getCurrentUser, logout, type CurrentUser } from "./api/auth";
import LoginPage from "./pages/Login/LoginPage";
import RegisterPage from "./pages/Register/RegisterPage";
import { createAppRoutes } from "./router/routes";
import { AUTH_ROUTES } from "./router/paths";
import styles from "./App.module.scss";

function AuthenticatedRoutes({ user, onLogout }: { user: CurrentUser; onLogout: () => void }) {
  return useRoutes(createAppRoutes(user, onLogout));
}

/** 应用入口只负责恢复登录态，具体页面交给路由配置。 */
export default function App() {
  const location = useLocation();
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    getCurrentUser()
      .then(setUser)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);
  if (loading)
    return (
      <div className={styles.screenCenter}>
        <Spin size="large" />
      </div>
    );
  if (!user)
    return location.pathname === AUTH_ROUTES.register ? (
      <RegisterPage onRegister={setUser} />
    ) : (
      <LoginPage onLogin={setUser} />
    );
  return <AuthenticatedRoutes user={user} onLogout={() => logout().then(() => setUser(null))} />;
}
