import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

const root = decodeURIComponent(new URL("./", import.meta.url).pathname);

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, root, "VITE_");
  return {
    root,
    plugins: [react()],
    server: {
      port: 5881,
      strictPort: true,
      // 默认连接本机后端；联调云端时通过 VITE_API_PROXY 覆盖。
      proxy: { "/api": env.VITE_API_PROXY || "http://127.0.0.1:8000" },
    },
  };
});
