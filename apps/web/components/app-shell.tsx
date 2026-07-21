"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import type { ReactNode } from "react";

import { getSession } from "@/lib/api";
import type { Session } from "@/lib/types";

const navigation = [
  { href: "/", label: "概览", icon: "⌂" },
  { href: "/members", label: "成员权限", icon: "♙" },
  { href: "/knowledge", label: "知识与商品", icon: "□" },
  { href: "/copilot", label: "客服 Copilot", icon: "◎" },
  { href: "/imports", label: "CSV 导入", icon: "▤" },
  { href: "/approvals", label: "人工审批", icon: "◇" },
];

const roleLabels: Record<Session["role"], string> = {
  owner: "负责人 · 完整管理",
  operator: "运营人员 · 运营支持",
  support: "客服人员 · 客服副驾",
  implementer: "实施人员 · 知识维护",
};

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [session, setSession] = useState<Session | null>(null);

  useEffect(() => {
    let active = true;
    async function loadSession() {
      if (!window.localStorage.getItem("fruit-agent-access-token")) {
        if (active) setSession(null);
        return;
      }
      try {
        const loaded = await getSession();
        if (active) setSession(loaded);
      } catch {
        if (active) setSession(null);
      }
    }
    void loadSession();
    window.addEventListener("fruit-agent-session-changed", loadSession);
    return () => {
      active = false;
      window.removeEventListener("fruit-agent-session-changed", loadSession);
    };
  }, []);

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
          <span>
            {session
              ? "当前租户：果序生鲜（华东）"
              : "当前租户：未建立演示会话"}
          </span>
          <span className="operator">
            {session ? roleLabels[session.role] : "请选择演示角色"}
          </span>
        </header>
        <main>{children}</main>
      </div>
    </div>
  );
}
