"use client";

import { AlertTriangle, Inbox } from "lucide-react";
import { useSyncExternalStore, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { SkeletonRows } from "@/components/ui/skeleton";

export interface PanelQuery<T> {
  data: T | undefined;
  isPending: boolean;
  isError: boolean;
  error: Error | null;
  refetch: () => unknown;
}

interface DataPanelProps<T> {
  query: PanelQuery<T>;
  children: (data: T) => ReactNode;
  isEmpty?: (data: T) => boolean;
  emptyMessage?: string;
  skeleton?: ReactNode;
  testId?: string;
}

const subscribeToNothing = () => () => {};

/**
 * False on the server and during hydration, true afterwards. Queries shared with the layout
 * (for example `/meta/stats`) can resolve before a page segment hydrates; gating on this keeps
 * the first client render equal to the server HTML.
 */
export function useHydrated(): boolean {
  return useSyncExternalStore(
    subscribeToNothing,
    () => true,
    () => false,
  );
}

export function EmptyState({ message }: { message: string }) {
  return (
    <div
      className="text-muted flex flex-col items-center gap-2 py-10 text-center"
      data-state="empty"
    >
      <Inbox className="text-muted size-6" aria-hidden />
      <p className="max-w-sm text-sm">{message}</p>
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: Error | null; onRetry: () => void }) {
  return (
    <div
      role="alert"
      className="flex flex-col items-center gap-3 py-10 text-center"
      data-state="error"
    >
      <AlertTriangle className="text-danger size-6" aria-hidden />
      <p className="text-muted max-w-md text-sm">{error?.message ?? "The request failed."}</p>
      <Button size="sm" onClick={onRetry}>
        Retry
      </Button>
    </div>
  );
}

/** One component for the four panel states of doc 10 section 2.3 rule 3. */
export function DataPanel<T>(props: DataPanelProps<T>) {
  const isHydrated = useHydrated();
  const body = isHydrated ? renderState(props) : (props.skeleton ?? <SkeletonRows />);
  return <div data-testid={props.testId}>{body}</div>;
}

function renderState<T>({
  query,
  children,
  isEmpty,
  emptyMessage = "No data available.",
  skeleton,
}: DataPanelProps<T>): ReactNode {
  if (query.isError && query.data === undefined) {
    return <ErrorState error={query.error} onRetry={() => void query.refetch()} />;
  }
  if (query.data === undefined) return skeleton ?? <SkeletonRows />;
  if (isEmpty?.(query.data)) return <EmptyState message={emptyMessage} />;
  return children(query.data);
}
