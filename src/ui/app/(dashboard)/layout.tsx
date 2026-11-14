import { Suspense, type ReactNode } from "react";
import { Footer } from "@/components/layout/Footer";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopBar } from "@/components/layout/TopBar";

export default function DashboardLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar />
        <main className="flex-1 overflow-y-auto">
          <div className="max-w-content mx-auto w-full px-6 pt-6">
            <Suspense fallback={null}>{children}</Suspense>
          </div>
          <Footer />
        </main>
      </div>
    </div>
  );
}
