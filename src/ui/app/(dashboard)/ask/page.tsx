import type { Metadata } from "next";
import { ChatPanel } from "@/components/ask/ChatPanel";
import { PageHeader } from "@/components/layout/PageHeader";

export const metadata: Metadata = { title: "Ask" };

export default function AskPage() {
  return (
    <>
      <PageHeader
        title="Ask"
        description="Cited question answering over the curated PSI corpus. Sentences without a supporting source are removed."
      />
      <ChatPanel />
    </>
  );
}
