import { ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";

interface PaginationProps {
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
}

export function Pagination({ page, pageSize, total, onPageChange }: PaginationProps) {
  const pageCount = Math.max(1, Math.ceil(total / pageSize));
  return (
    <nav
      aria-label="Pagination"
      className="text-caption text-muted flex items-center justify-between gap-4 pt-4"
    >
      <span className="mono">
        {total} total, page {page} of {pageCount}
      </span>
      <div className="flex gap-2">
        <Button size="sm" disabled={page <= 1} onClick={() => onPageChange(page - 1)}>
          <ChevronLeft className="size-4" aria-hidden /> Previous
        </Button>
        <Button size="sm" disabled={page >= pageCount} onClick={() => onPageChange(page + 1)}>
          Next <ChevronRight className="size-4" aria-hidden />
        </Button>
      </div>
    </nav>
  );
}
