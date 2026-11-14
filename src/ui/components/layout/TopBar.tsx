"use client";

import { ExternalLink, Search } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { StatusBadge } from "@/components/architecture/StatusBadge";
import { Badge } from "@/components/ui/badge";
import { useStats, useStatus } from "@/lib/api/hooks";
import type { ComponentStatus } from "@/lib/api/types";
import { PSI_URL } from "@/lib/constants";

const EDITABLE_TAGS = new Set(["INPUT", "TEXTAREA", "SELECT"]);

function useSlashFocus(inputRef: React.RefObject<HTMLInputElement | null>) {
  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      if (event.key !== "/" || (target && EDITABLE_TAGS.has(target.tagName))) return;
      event.preventDefault();
      inputRef.current?.focus();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [inputRef]);
}

function GlobalSearch() {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [text, setText] = useState("");
  useSlashFocus(inputRef);

  function submit(event: FormEvent) {
    event.preventDefault();
    const query = text.trim();
    router.push(query ? `/explorer?q=${encodeURIComponent(query)}` : "/explorer");
  }

  return (
    <form onSubmit={submit} role="search" className="relative w-full max-w-md">
      <Search className="text-muted absolute top-2.5 left-3 size-4" aria-hidden />
      <input
        ref={inputRef}
        value={text}
        onChange={(event) => setText(event.target.value)}
        placeholder="Search investigations"
        aria-label="Search investigations"
        className="rounded-control border-line bg-surface2 text-fg placeholder:text-muted hover:border-line-strong h-9 w-full border pr-10 pl-9 text-sm"
      />
      <kbd className="mono border-line text-muted absolute top-2 right-3 rounded border px-1.5 text-xs">
        /
      </kbd>
    </form>
  );
}

function LlmModeBadge({ llm }: { llm: ComponentStatus | undefined }) {
  if (!llm) return <Badge>LLM: unknown</Badge>;
  const provider = llm.provider ?? llm.status;
  const text = provider === "ollama" && llm.model ? `ollama · ${llm.model}` : provider;
  return (
    <span className="flex items-center gap-2">
      <span className="text-muted text-xs">LLM</span>
      <StatusBadge status={llm.status} label={text} />
    </span>
  );
}

export function TopBar() {
  const status = useStatus();
  const stats = useStats();
  const llm = status.data?.components.find((component) => component.id === "C-LLM");
  const mode = stats.data?.ingest_mode;

  return (
    <header className="border-line bg-bg flex h-14 shrink-0 items-center gap-4 border-b px-6">
      <GlobalSearch />
      <div className="ml-auto flex items-center gap-4">
        <LlmModeBadge llm={llm} />
        <Badge>
          {mode ?? "dataset"}
          {stats.data ? ` · ${stats.data.investigations} investigations` : ""}
        </Badge>
        <a
          href={PSI_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="text-muted hover:text-fg flex items-center gap-1.5 text-sm transition-colors"
        >
          NASA PSI <ExternalLink className="size-3.5" aria-hidden />
        </a>
      </div>
    </header>
  );
}
