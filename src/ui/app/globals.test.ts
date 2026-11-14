// @vitest-environment node
import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { LENS_COLORS, PHASE_COLORS } from "@/lib/constants";

const UI_ROOT = path.resolve(__dirname, "..");
const DOC_10 = path.resolve(UI_ROOT, "..", "..", "docs", "architecture", "10-ui-architecture.md");
const GLOBALS_CSS = readFileSync(path.join(UI_ROOT, "app", "globals.css"), "utf-8");
const DOC_TEXT = readFileSync(DOC_10, "utf-8");
/** Rows of the doc 10 section 2.1 table; the fuel-phase row holds three tokens. */
const DOCUMENTED_TOKEN_COUNT = 17;

/** Lower-cases hex digits and removes spaces so `rgba(249, 115, 22, 0.12)` equals `rgba(249,115,22,0.12)`. */
function normalize(value: string): string {
  return value.replace(/\s+/g, "").toLowerCase();
}

function section(text: string, heading: string, nextHeading: string): string {
  const start = text.indexOf(heading);
  return text.slice(start, text.indexOf(nextHeading, start));
}

/** Token table of doc 10 section 2.1 as [name, value] pairs. */
function documentedTokens(): [string, string][] {
  const table = section(DOC_TEXT, "### 2.1 Tokens", "Lens colours");
  return table
    .split("\n")
    .filter((line) => line.startsWith("| `--"))
    .flatMap((line) => {
      const [names = "", values = ""] = line.split("|").slice(1, 3);
      const nameList = names.match(/--[a-z0-9-]+/g) ?? [];
      const valueList = values.match(/#[0-9A-Fa-f]{6}|rgba\([^)]*\)/g) ?? [];
      return nameList.map((name, index) => [name, valueList[index] ?? ""] as [string, string]);
    });
}

/** `--name: value;` declarations of the `:root` block of globals.css. */
function cssVariables(): Map<string, string> {
  const root = /:root\s*{([\s\S]*?)}/.exec(GLOBALS_CSS)?.[1] ?? "";
  const declarations = root.matchAll(/(--[a-z0-9-]+)\s*:\s*([^;]+);/g);
  return new Map([...declarations].map(([, name = "", value = ""]) => [name, value.trim()]));
}

function resolve(variables: Map<string, string>, value: string): string {
  const reference = /^var\((--[a-z0-9-]+)\)$/.exec(value)?.[1];
  return reference ? resolve(variables, variables.get(reference) ?? "") : normalize(value);
}

function valueOf(name: string): string {
  const variables = cssVariables();
  return resolve(variables, variables.get(name) ?? "");
}

function variableName(cssValue: string): string {
  return /^var\((--[a-z0-9-]+)\)$/.exec(cssValue)?.[1] ?? cssValue;
}

const TOKENS = documentedTokens();

describe("design tokens in app/globals.css (doc 10 section 2.1)", () => {
  it("NFR-03: the token table of doc 10 is parsed completely", () => {
    expect(TOKENS).toHaveLength(DOCUMENTED_TOKEN_COUNT);
    TOKENS.forEach(([, value]) => expect(value).not.toBe(""));
  });

  it.each(TOKENS)("NFR-03: %s is defined as %s", (name, value) => {
    expect(valueOf(name)).toBe(normalize(value));
  });

  it("NFR-03: lens colours are habitat #F97316, modeling #38BDF8, controls #34D399", () => {
    expect(valueOf(variableName(LENS_COLORS.habitat))).toBe("#f97316");
    expect(valueOf(variableName(LENS_COLORS.modeling))).toBe("#38bdf8");
    expect(valueOf(variableName(LENS_COLORS.controls))).toBe("#34d399");
  });

  it("NFR-03: fuel-phase colours used by charts and badges are the gas, liquid and solid tokens", () => {
    expect(PHASE_COLORS).toEqual({
      gas: "var(--gas)",
      liquid: "var(--liquid)",
      solid: "var(--solid)",
    });
  });
});

describe("architecture page colours (doc 10 sections 2.1 and 6.3)", () => {
  it.each([
    ["--kind-agents", "#A78BFA"],
    ["--kind-ingestion", "#FB7185"],
    ["--edge", "#475569"],
    ["--edge-llm", "#A78BFA"],
  ])("FR-13: %s is %s", (name, value) => {
    expect(valueOf(name)).toBe(normalize(value));
  });

  it.each([
    ["--kind-ui", "--cool"],
    ["--kind-api", "--success"],
    ["--kind-services", "--accent"],
    ["--kind-data", "--warning"],
  ])(
    "FR-13: %s reuses the %s token (UI blue, API green, services orange, data amber)",
    (name, token) => {
      expect(valueOf(name)).toBe(valueOf(token));
    },
  );

  it("FR-13: the external strip is defined", () => {
    expect(valueOf("--kind-external")).not.toBe("");
  });
});

describe("dark theme quality rules (doc 10 section 2.3 rule 1)", () => {
  it("NFR-03: no token is pure black or pure white", () => {
    const forbidden = ["#000000", "#000", "#ffffff", "#fff"];
    [...cssVariables().keys()].forEach((name) => expect(forbidden).not.toContain(valueOf(name)));
  });
});
