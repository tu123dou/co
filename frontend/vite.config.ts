import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        // 框架和 UI 库独立缓存，业务代码更新时浏览器无需重复下载大体积依赖。
        manualChunks: {
          "react-vendor": ["react", "react-dom", "react-router-dom"],
          "antd-vendor": ["antd", "@ant-design/icons"],
        },
      },
    },
  },
  server: {
    port: 5881,
    strictPort: true,
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
});
