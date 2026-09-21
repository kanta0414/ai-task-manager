import { fileURLToPath } from "node:url";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  test: {
    include: ["src/**/*.test.ts", "src/**/*.test.tsx"],
    // 既定は node。DOM が必要なテストはファイル先頭の
    // `// @vitest-environment jsdom` で切り替える
    // （ロジックのテストが DOM に依存していないことを保てる）
    environment: "node",
    setupFiles: ["./vitest.setup.ts"],
  },
});
