import { ExternalLink } from "lucide-react";
import type { SourceRef } from "@/lib/api/types";

function linkText(source: SourceRef): string {
  const title = source.title ?? source.uri.replace(/^https?:\/\//, "");
  return source.locator ? `${title} (${source.locator})` : title;
}

function isOpenable(uri: string): boolean {
  return uri.startsWith("https://") || uri.startsWith("http://");
}

/** A provenance link; S3 keys are shown as text because browsers cannot open them. */
export function SourceLink({ source }: { source: SourceRef }) {
  const text = linkText(source);
  if (!isOpenable(source.uri)) {
    return (
      <span className="mono text-muted text-xs" title={source.quote ?? source.uri}>
        {text}
      </span>
    );
  }
  return (
    <a
      href={source.uri}
      target="_blank"
      rel="noopener noreferrer"
      title={source.quote ?? source.uri}
      className="text-cool inline-flex max-w-full items-center gap-1 text-xs transition-colors hover:underline"
    >
      <span className="truncate">{text}</span>
      <ExternalLink className="size-3 shrink-0" aria-hidden />
    </a>
  );
}
