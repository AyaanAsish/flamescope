"""Ask: streaming answer, citation chips, sources panel, related links, fixed refusal.

Requirements FR-11 (cited question answering) and FR-15 (provenance); documents 05 section 10
(SSE events and the fixed out-of-corpus sentence) and 10 section 5 (`/ask`), call flow CF-09.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterator
from typing import Any
from urllib.parse import quote

import httpx
import pytest
from playwright.sync_api import Locator, Page, expect

pytestmark = pytest.mark.e2e

DOC_05 = "05-api-specification.md"
FIXED_SENTENCE = re.compile(r'the answer is the fixed sentence "([^"]+)"')
OFF_CORPUS = re.compile(r'off-corpus questions \("([^"]+)"')
# The mock answers in one burst; a live model streams over seconds. This init script paces the
# `/ask` body one SSE frame per task at the browser boundary, so the UI's own parser and renderer
# show the draft growing before the verified answer replaces it.
FRAME_PAUSE_MS = 40
PACE_ASK_FRAMES = """(pauseMs) => {
  const original = window.fetch;
  window.fetch = async (input, init) => {
    const response = await original(input, init);
    const url = String(input instanceof Request ? input.url : input);
    if (!url.endsWith('/api/v1/ask')) return response;
    const frames = (await response.text()).split(/(?<=\\n\\n)/);
    const encoder = new TextEncoder();
    const body = new ReadableStream({async start(controller) {
      for (const frame of frames) {
        controller.enqueue(encoder.encode(frame));
        await new Promise((resolve) => setTimeout(resolve, pauseMs));
      }
      controller.close();
    }});
    return new Response(body, {status: response.status, headers: response.headers});
  };
}"""
RECORD_DRAFT_LENGTHS = """() => {
  window.__draftLengths = [];
  const observer = new MutationObserver(() => {
    const answer = document.querySelector('[data-testid=ask-answer]');
    if (!answer || answer.querySelector('[data-testid=citation-chip]')) return;
    window.__draftLengths.push(answer.innerText.trim().length);
  });
  const options = {subtree: true, childList: true, characterData: true};
  observer.observe(document.querySelector('main'), options);
}"""


def _ask(api: httpx.Client, question: str) -> dict[str, Any]:
    """`POST /ask` events keyed by name (`citations`, `related`, ...)."""
    body = {"question": question, "filters": {"investigations": []}}
    text = api.post("/ask", json=body).text
    events: dict[str, Any] = {}
    for frame in text.replace("\r\n", "\n").split("\n\n"):
        lines = dict(line.split(": ", 1) for line in frame.splitlines() if ": " in line)
        if "event" in lines:
            events[lines["event"]] = json.loads(lines["data"])
    return events


def _suggestions(page: Page) -> Locator:
    return page.locator("main li").get_by_role("button")


@pytest.fixture
def streamed_answer(goto: Callable[..., Page]) -> Iterator[tuple[Page, str]]:
    """The Ask page after a suggested question was answered as a paced stream."""
    page = goto("/ask")
    question = _suggestions(page).first.inner_text()
    page.evaluate(PACE_ASK_FRAMES, FRAME_PAUSE_MS)
    page.evaluate(RECORD_DRAFT_LENGTHS)
    _suggestions(page).first.click()
    expect(page.get_by_test_id("ask-input")).to_be_disabled()
    expect(page.get_by_test_id("citation-chip").first).to_be_visible()
    yield page, question


def test_suggested_questions_present(goto: Callable[..., Page]) -> None:
    """FR-11: before the first question the page offers suggested questions and empty sources."""
    page = goto("/ask")
    assert _suggestions(page).count() > 0
    expect(page.get_by_test_id("ask-sources")).to_contain_text("Sources appear here")


def test_answer_streams_then_shows_cited_answer(
    streamed_answer: tuple[Page, str], api: httpx.Client
) -> None:
    """FR-11: the draft grows token by token, then the verified sentences with their chips."""
    page, question = streamed_answer
    lengths = [length for length in page.evaluate("() => window.__draftLengths") if length]
    assert len(set(lengths)) >= 2 and lengths == sorted(lengths), lengths
    sentences = _ask(api, question)["citations"]["sentences"]
    answer = page.get_by_test_id("ask-answer")
    for sentence in sentences:
        expect(answer).to_contain_text(sentence["text"])
    citations = sum(len(sentence["citations"]) for sentence in sentences)
    expect(answer.get_by_test_id("citation-chip")).to_have_count(citations)


def test_input_disabled_while_streaming_then_enabled(streamed_answer: tuple[Page, str]) -> None:
    """FR-11: the question input is disabled during the stream and enabled after `done`."""
    page, _ = streamed_answer
    expect(page.get_by_test_id("ask-input")).to_be_enabled()


def test_citation_chip_highlights_source(
    streamed_answer: tuple[Page, str], api: httpx.Client
) -> None:
    """FR-15: a chip marks its retrieved chunk in the sources panel and shows a working link."""
    page, question = streamed_answer
    events = _ask(api, question)
    source = events["citations"]["sentences"][0]["citations"][0]
    page.get_by_test_id("citation-chip").first.click()
    expect(page.get_by_test_id("citation-chip").first).to_have_attribute("aria-pressed", "true")
    sources = page.get_by_test_id("ask-sources")
    retrieved = [chunk["chunk_id"] for chunk in events["meta"]["retrieved"]]
    expect(sources.locator("li")).to_have_count(len(retrieved))
    expect(sources.locator("li[aria-current=true]")).to_have_count(
        int(source["chunk_id"] in retrieved)
    )
    link = sources.locator(f"a[href='{source['uri']}']")
    expect(link).to_have_attribute("target", "_blank")
    with page.context.expect_page() as opened:
        link.click()
    assert opened.value.url.startswith(source["uri"].split("?")[0])


def test_related_investigations_link_to_detail(
    streamed_answer: tuple[Page, str], api: httpx.Client
) -> None:
    """FR-11: the related investigations of the answer link to their detail pages."""
    page, question = streamed_answer
    related = _ask(api, question)["related"]["investigations"]
    answer = page.get_by_test_id("ask-answer")
    links = answer.locator("a[href^='/investigations/']")
    expect(links).to_have_count(len(related))
    for index, acronym in enumerate(related):
        expect(links.nth(index)).to_have_attribute(
            "href", f"/investigations/{quote(acronym, safe='')}"
        )
    links.first.click()
    expect(page.get_by_test_id("detail-header")).to_contain_text(related[0])


def test_out_of_corpus_question_gets_fixed_sentence(
    goto: Callable[..., Page], doc_section: Callable[[str, str], str]
) -> None:
    """FR-11: an off-corpus question (doc 05 s10) shows only the fixed sentence, no chips."""
    section = " ".join(doc_section(DOC_05, "## 10. Ask (SSE)").split())
    fixed, question = FIXED_SENTENCE.search(section), OFF_CORPUS.search(section)
    assert fixed is not None and question is not None
    page = goto("/ask")
    page.get_by_test_id("ask-input").fill(question.group(1))
    page.get_by_test_id("ask-input").press("Enter")
    answer = page.get_by_test_id("ask-answer")
    expect(answer).to_have_text(fixed.group(1))
    expect(answer.get_by_test_id("citation-chip")).to_have_count(0)


def test_enter_submits_and_shift_enter_adds_line(goto: Callable[..., Page]) -> None:
    """FR-11: Shift+Enter inserts a line break; Enter submits and clears the input."""
    page = goto("/ask")
    field = page.get_by_test_id("ask-input")
    field.type("Which hardware")
    field.press("Shift+Enter")
    field.type("is shared?")
    expect(field).to_have_value("Which hardware\nis shared?")
    expect(page.get_by_test_id("ask-answer")).to_have_count(0)
    field.press("Enter")
    expect(page.get_by_test_id("ask-answer")).to_have_count(1)
    expect(field).to_have_value("")
    expect(field).to_be_enabled()
