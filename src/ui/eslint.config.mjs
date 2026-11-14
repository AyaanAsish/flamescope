import nextVitals from "eslint-config-next/core-web-vitals";
import nextTypescript from "eslint-config-next/typescript";

const complexityRules = {
  complexity: ["error", 10],
  "max-depth": ["error", 3],
  "max-params": ["error", 4],
  "max-nested-callbacks": ["error", 3],
  "max-lines-per-function": ["error", { max: 80, skipBlankLines: true, skipComments: true }],
};

const config = [
  ...nextVitals,
  ...nextTypescript,
  { ignores: [".next/**", "node_modules/**", "next-env.d.ts", "lib/api/types.generated.ts"] },
  { rules: complexityRules },
];

export default config;
