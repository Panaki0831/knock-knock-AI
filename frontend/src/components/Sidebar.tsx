"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const navItems = [
  { href: "/dashboard", label: "Dashboard", icon: "BarChart3" },
  { href: "/articles", label: "Articles", icon: "FileText" },
  { href: "/calendar", label: "Calendar", icon: "Calendar" },
  { href: "/knowledge", label: "Knowledge Base", icon: "BookOpen" },
  { href: "/research", label: "Research History", icon: "Search" },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-64 bg-brand-900 text-white flex flex-col">
      {/* Logo */}
      <div className="p-6 border-b border-white/10">
        <h1 className="text-xl font-bold tracking-tight">knock knock AI</h1>
        <p className="text-xs text-blue-200 mt-1">Content Marketing Platform</p>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-4 space-y-1">
        {navItems.map((item) => {
          const isActive = pathname?.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                isActive
                  ? "bg-white/15 text-white"
                  : "text-blue-100 hover:bg-white/10 hover:text-white"
              }`}
            >
              <span className="text-lg">{getIcon(item.icon)}</span>
              {item.label}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="p-4 border-t border-white/10 text-xs text-blue-200">
        <p>SAMURAI ARCHITECTS Inc.</p>
        <p className="mt-0.5">v0.1.0</p>
      </div>
    </aside>
  );
}

function getIcon(name: string): string {
  const icons: Record<string, string> = {
    BarChart3: "\u{1F4CA}",
    FileText: "\u{1F4DD}",
    Calendar: "\u{1F4C5}",
    BookOpen: "\u{1F4DA}",
    Search: "\u{1F50D}",
  };
  return icons[name] || "\u{25CF}";
}
