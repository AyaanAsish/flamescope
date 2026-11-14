import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 text-center">
      <p className="mono text-muted text-sm">404</p>
      <h1 className="text-2xl font-semibold">Page not found</h1>
      <p className="text-muted max-w-sm text-sm">That route does not exist in FlameScope.</p>
      <Button asChild variant="primary">
        <Link href="/">Back to overview</Link>
      </Button>
    </div>
  );
}
