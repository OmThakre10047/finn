"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const TABS = [
  { href: "/", label: "Today", icon: "◉" },
  { href: "/radar", label: "Radar", icon: "⚡" },
  { href: "/research", label: "Research", icon: "◎" },
  { href: "/settings", label: "Settings", icon: "⚙" },
];

export function TabBar() {
  const path = usePathname();
  return (
    <nav className="fixed inset-x-0 bottom-0 z-50 border-t border-zinc-200 bg-white/90 backdrop-blur dark:border-ink-700 dark:bg-ink-950/90">
      <div className="mx-auto flex max-w-lg">
        {TABS.map((t) => {
          const active = path === t.href;
          return (
            <Link
              key={t.href}
              href={t.href}
              className={`flex flex-1 flex-col items-center gap-0.5 py-2.5 text-[11px] font-medium ${
                active ? "text-accent" : "text-zinc-500 dark:text-zinc-400"
              }`}
            >
              <span className="text-base leading-none">{t.icon}</span>
              {t.label}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
