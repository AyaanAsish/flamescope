"use client";

import {
  GitCompareArrows,
  Globe2,
  LayoutDashboard,
  MessageSquareText,
  Network,
  PanelLeftClose,
  PanelLeftOpen,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  Table2,
  Trophy,
  type LucideIcon,
} from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { NAV_ITEMS, type NavIcon } from "@/lib/constants";
import { useUiStore } from "@/lib/store";
import { cn } from "@/lib/utils";

const ICONS: Record<NavIcon, LucideIcon> = {
  overview: LayoutDashboard,
  explorer: Search,
  ranking: Trophy,
  compare: GitCompareArrows,
  scenario: SlidersHorizontal,
  extract: Table2,
  safety: ShieldCheck,
  earth: Globe2,
  ask: MessageSquareText,
  architecture: Network,
};

function isActive(pathname: string, href: string): boolean {
  return href === "/" ? pathname === "/" : pathname.startsWith(href);
}

export function Sidebar() {
  const pathname = usePathname();
  const collapsed = useUiStore((state) => state.sidebarCollapsed);
  const toggle = useUiStore((state) => state.toggleSidebar);
  const ToggleIcon = collapsed ? PanelLeftOpen : PanelLeftClose;

  return (
    <aside
      className={cn(
        "border-line bg-surface1 flex shrink-0 flex-col border-r transition-[width]",
        collapsed ? "w-16" : "w-60",
      )}
    >
      <div className="border-line flex h-14 items-center gap-3 border-b px-4">
        <Image src="/logo.svg" alt="" width={28} height={28} priority />
        {collapsed ? null : (
          <span className="text-base font-semibold tracking-tight">FlameScope</span>
        )}
      </div>
      <nav aria-label="Main" className="flex-1 space-y-0.5 overflow-y-auto p-2">
        {NAV_ITEMS.map((item) => {
          const Icon = ICONS[item.icon];
          const active = isActive(pathname, item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              title={item.label}
              aria-current={active ? "page" : undefined}
              className={cn(
                "rounded-control relative flex h-9 items-center gap-3 px-3 text-sm font-medium transition-colors",
                active ? "bg-surface2 text-fg" : "text-muted hover:bg-surface2/60 hover:text-fg",
              )}
            >
              {active ? (
                <span className="bg-accent absolute inset-y-1.5 left-0 w-0.5 rounded-full" />
              ) : null}
              <Icon className={cn("size-4 shrink-0", active ? "text-accent" : "")} aria-hidden />
              {collapsed ? <span className="sr-only">{item.label}</span> : item.label}
            </Link>
          );
        })}
      </nav>
      <div className="border-line border-t p-2">
        <button
          type="button"
          onClick={toggle}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          className="rounded-control text-muted hover:bg-surface2 hover:text-fg flex h-9 w-full items-center gap-3 px-3 text-sm"
        >
          <ToggleIcon className="size-4 shrink-0" aria-hidden />
          {collapsed ? null : "Collapse"}
        </button>
      </div>
    </aside>
  );
}
