import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@": new URL("./", import.meta.url).pathname } },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./vitest.setup.ts"],
    clearMocks: true,
    include: ["**/*.test.{ts,tsx}"],
    exclude: ["node_modules", ".next"],
    coverage: {
      provider: "v8",
      include: ["lib/**"],
      exclude: ["lib/**/*.test.ts", "lib/api/types*.ts"],
      reporter: ["text-summary"],
      thresholds: { lines: 80 },
    },
  },
});
