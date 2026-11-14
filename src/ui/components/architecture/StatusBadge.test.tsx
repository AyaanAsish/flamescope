import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StatusBadge, statusTone } from "@/components/architecture/StatusBadge";

/** Doc 10 section 6.3: green dot up, amber dot mock or idle, red dot down. */
const STATUS_DOTS: [string, string][] = [
  ["up", "bg-success"],
  ["mock", "bg-warning"],
  ["idle", "bg-warning"],
  ["down", "bg-danger"],
];

function dotOf(badge: HTMLElement): Element | null {
  return badge.querySelector("[aria-hidden]");
}

describe("StatusBadge (doc 10 section 6.3, doc 05 section 3 /meta/status)", () => {
  it.each(STATUS_DOTS)("FR-13: status %s shows a %s dot and its text label", (status, dotClass) => {
    render(<StatusBadge status={status} />);
    const badge = screen.getByText(status);
    expect(badge).toHaveAttribute("data-status", status);
    expect(dotOf(badge)).toHaveClass(dotClass);
  });

  it("FR-13: an unknown status (no /meta/status yet) is labelled unknown with a neutral dot", () => {
    render(<StatusBadge status={undefined} />);
    const badge = screen.getByText("unknown");
    expect(badge).toHaveAttribute("data-status", "unknown");
    expect(dotOf(badge)).toHaveClass("bg-faint");
    expect(statusTone("something-else")).toBe("neutral");
  });

  it("FR-13: a custom label (for example the LLM model) is shown next to the dot", () => {
    render(<StatusBadge status="up" label="ollama · qwen2.5:0.5b" />);
    expect(screen.getByText("ollama · qwen2.5:0.5b")).toHaveAttribute("data-status", "up");
  });
});
