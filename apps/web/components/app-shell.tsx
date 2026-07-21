"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

const navigation = [
  { href: "/", label: "概览", icon: "⌂" },
  { href: "/members", label: "成员权限", icon: "♙" },
  { href: "/knowledge", label: "知识与商品", icon: "□" },
  { href: "/copilot", label: "客服 Copilot", icon: "◎" },
  { href: "/imports", label: "CSV 导入", icon: "▤" },
  { href: "/approvals", label: "人工审批", icon: "◇" },
];

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="app-frame">
      <aside className="sidebar">
        <Link className="brand" href="/">
          <span className="brand-mark" aria-hidden="true">
            果
          </span>
          果序 Agent
        </Link>
        <nav aria-label="主导航">
          {navigation.map((item) => (
            <Link
              aria-current={pathname === item.href ? "page" : undefined}
              className={`nav-link ${
                pathname === item.href ? "is-active" : ""
              }`}
              href={item.href}
              key={item.href}
            >
              <span className="nav-icon" aria-hidden="true">
                {item.icon}
              </span>
              {item.label}
            </Link>
          ))}
        </nav>
        <p className="sidebar-note">人工确认优先</p>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <span>当前租户：果序生鲜（华东）</span>
          <span className="operator">运 · 运营支持</span>
        </header>
        <main>{children}</main>
      </div>
    </div>
  );
}
