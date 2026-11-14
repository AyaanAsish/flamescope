import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import AskPage from "@/app/(dashboard)/ask/page";
import { streamAsk } from "@/lib/api/sse";
import type { AskCitations, AskHandlers, AskMeta } from "@/lib/api/types";
import { SOURCE } from "@/test-fixtures";
import { apiFailure, renderWithQuery } from "@/test-utils";

vi.mock("@/lib/api/sse", () => ({ streamAsk: vi.fn() }));

/** Doc 05 section 10 fixed sentence for out-of-corpus questions. */
const INSUFFICIENT = "The curated PSI corpus does not contain enough information to answer that.";
const QUESTION = "Which experiments tested solids above 30% oxygen?";
const META: AskMeta = {
  request_id: "req-1",
  retrieved: [{ chunk_id: 1, acronym: "BASS-II", doc_title: "BASS-II overview", score: 0.71 }],
};
const CITATIONS: AskCitations = {
  sentences: [
    { text: "BASS-II burned solids at 21 % oxygen.", citations: [SOURCE], supported: true },
  ],
  dropped: 1,
};

type Script = (handlers: AskHandlers) => Promise<void>;

function scriptStream(script: Script): void {
  vi.mocked(streamAsk).mockImplementation((_body, handlers) => script(handlers));
}

async function ask(question = QUESTION) {
  renderWithQuery(<AskPage />);
  fireEvent.change(screen.getByTestId("ask-input"), { target: { value: question } });
  fireEvent.click(screen.getByRole("button", { name: "Ask" }));
  return screen.findByTestId("ask-answer");
}

const fullAnswer: Script = async (handlers) => {
  handlers.onMeta?.(META);
  handlers.onToken?.("BASS-II burned ");
  handlers.onCitations?.(CITATIONS);
  handlers.onRelated?.(["BASS-II", "CFI-G"]);
  handlers.onDone?.();
};

describe("Ask page /ask (doc 10 section 5, CF-09)", () => {
  it("FR-11: empty state offers suggested questions and an empty sources panel", () => {
    renderWithQuery(<AskPage />);
    expect(screen.getByTestId("ask-input")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: QUESTION })).toBeInTheDocument();
    expect(
      within(screen.getByTestId("ask-sources")).getByText(/appear here after you ask/),
    ).toBeInTheDocument();
    expect(screen.queryByTestId("ask-answer")).not.toBeInTheDocument();
  });

  it("FR-11: loading state shows a waiting skeleton while the stream is open", async () => {
    scriptStream(() => new Promise(() => undefined));
    const answer = await ask();
    expect(within(answer).getByRole("status", { name: "Waiting for answer" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /stop/i })).toBeInTheDocument();
  });

  it("FR-11: an error event shows the message and keeps the retrieved sources visible", async () => {
    scriptStream(async (handlers) => {
      handlers.onMeta?.(META);
      handlers.onError?.({ code: "llm_unavailable", message: "LLM provider failed." });
    });
    const answer = await ask();
    expect(await within(answer).findByRole("alert")).toHaveTextContent("LLM provider failed.");
    expect(
      within(screen.getByTestId("ask-sources")).getByText("BASS-II overview"),
    ).toBeInTheDocument();
  });

  it("FR-11: an HTTP failure before the stream is shown as an error", async () => {
    scriptStream(() => Promise.reject(apiFailure(422, "question is required")));
    const answer = await ask();
    expect(await within(answer).findByRole("alert")).toHaveTextContent("question is required");
  });

  it("FR-15: data state replaces the draft with verified sentences and citation chips", async () => {
    scriptStream(fullAnswer);
    const answer = await ask();
    const chip = await within(answer).findByTestId("citation-chip");
    expect(within(answer).getByText(CITATIONS.sentences[0]!.text)).toBeInTheDocument();
    expect(within(answer).getByText(/1 sentence\(s\) were removed/)).toBeInTheDocument();
    expect(within(answer).getByRole("link", { name: "CFI-G" })).toBeInTheDocument();
    fireEvent.click(chip);
    const sources = screen.getByTestId("ask-sources");
    await waitFor(() => expect(within(sources).getByText(SOURCE.quote!)).toBeInTheDocument());
  });

  it("FR-11: an out-of-corpus question shows the fixed sentence without citations", async () => {
    scriptStream(async (handlers) => {
      handlers.onMeta?.({ request_id: "req-2", retrieved: [] });
      handlers.onCitations?.({
        sentences: [{ text: INSUFFICIENT, citations: [], supported: true }],
        dropped: 0,
      });
      handlers.onDone?.();
    });
    const answer = await ask("What is the boiling point of lunar regolith?");
    expect(await within(answer).findByText(INSUFFICIENT)).toBeInTheDocument();
    expect(within(answer).queryByTestId("citation-chip")).not.toBeInTheDocument();
  });

  it("FR-11: the question is posted with the documented request shape", async () => {
    scriptStream(fullAnswer);
    await ask();
    expect(vi.mocked(streamAsk)).toHaveBeenCalledWith(
      { question: QUESTION, filters: { investigations: [] } },
      expect.any(Object),
      expect.any(AbortSignal),
    );
  });
});
