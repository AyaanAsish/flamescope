"use client";

import { useEffect, useId, useState } from "react";
import { ErrorState } from "@/components/ui/panel-state";
import { Skeleton } from "@/components/ui/skeleton";

const TOKEN_NAMES = [
  "--bg",
  "--surface-1",
  "--surface-2",
  "--border",
  "--border-strong",
  "--text",
  "--text-muted",
  "--text-faint",
  "--accent",
  "--cool",
] as const;
type TokenName = (typeof TOKEN_NAMES)[number];

/** Mermaid cannot resolve CSS variables, so token values are read from the document at render time. */
function readTokens(): Record<TokenName, string> {
  const style = getComputedStyle(document.documentElement);
  return Object.fromEntries(
    TOKEN_NAMES.map((name) => [name, style.getPropertyValue(name).trim()]),
  ) as Record<TokenName, string>;
}

function themeVariables(tokens: Record<TokenName, string>, fontFamily: string) {
  return {
    background: tokens["--bg"],
    fontFamily,
    primaryColor: tokens["--surface-2"],
    primaryTextColor: tokens["--text"],
    primaryBorderColor: tokens["--border-strong"],
    secondaryColor: tokens["--surface-1"],
    tertiaryColor: tokens["--surface-1"],
    lineColor: tokens["--text-faint"],
    textColor: tokens["--text"],
    actorBkg: tokens["--surface-2"],
    actorBorder: tokens["--border-strong"],
    actorTextColor: tokens["--text"],
    actorLineColor: tokens["--border-strong"],
    signalColor: tokens["--text-muted"],
    signalTextColor: tokens["--text"],
    labelBoxBkgColor: tokens["--surface-2"],
    labelBoxBorderColor: tokens["--border-strong"],
    labelTextColor: tokens["--text"],
    loopTextColor: tokens["--text-muted"],
    noteBkgColor: tokens["--surface-1"],
    noteBorderColor: tokens["--accent"],
    noteTextColor: tokens["--text"],
    activationBkgColor: tokens["--surface-2"],
    activationBorderColor: tokens["--cool"],
  };
}

async function renderSvg(renderId: string, source: string): Promise<string> {
  const mermaid = (await import("mermaid")).default;
  const fontFamily = getComputedStyle(document.body).fontFamily;
  mermaid.initialize({
    startOnLoad: false,
    securityLevel: "strict",
    theme: "base",
    themeVariables: themeVariables(readTokens(), fontFamily),
    sequence: { mirrorActors: false, useMaxWidth: true },
  });
  const { svg } = await mermaid.render(renderId, source);
  return svg;
}

interface RenderResult {
  key: string;
  svg?: string;
  error?: string;
}

const RENDER_FAILURE = "The diagram could not be rendered.";

function DiagramBody({ result, onRetry }: { result: RenderResult | null; onRetry: () => void }) {
  if (!result) return <Skeleton className="h-64" />;
  if (result.error) return <ErrorState error={new Error(result.error)} onRetry={onRetry} />;
  return <div dangerouslySetInnerHTML={{ __html: result.svg ?? "" }} />;
}

export function SequenceDiagram({ flowId, source }: { flowId: string; source: string }) {
  const reactId = useId().replace(/[^a-zA-Z0-9]/g, "");
  const [attempt, setAttempt] = useState(0);
  const [result, setResult] = useState<RenderResult | null>(null);
  const key = `${flowId}|${source.length}|${attempt}`;

  useEffect(() => {
    let isCurrent = true;
    renderSvg(`mmd-${flowId}-${reactId}-${attempt}`, source)
      .then((svg) => isCurrent && setResult({ key, svg }))
      .catch(
        (error: unknown) =>
          isCurrent &&
          setResult({ key, error: error instanceof Error ? error.message : RENDER_FAILURE }),
      );
    return () => {
      isCurrent = false;
    };
  }, [flowId, source, reactId, attempt, key]);

  return (
    <div
      data-testid="arch-sequence"
      data-flow={flowId}
      className="mermaid-host rounded-card border-line bg-bg min-h-64 overflow-auto border p-4"
    >
      <DiagramBody
        result={result?.key === key ? result : null}
        onRetry={() => setAttempt((value) => value + 1)}
      />
    </div>
  );
}
