"use client";

import { FormEvent, useState } from "react";

import { createDemoSession } from "@/lib/api";
import type { DemoRole } from "@/lib/types";

const roleLabels: Record<DemoRole, string> = {
  owner: "负责人（完整管理权限）",
  operator: "运营人员（推荐演示）",
  support: "客服人员（客服副驾）",
  implementer: "实施人员（知识维护）",
};

export function DemoEntry({ enabled }: { enabled: boolean }) {
  const [role, setRole] = useState<DemoRole>("operator");
  const [submitting, setSubmitting] = useState(false);
  const [failed, setFailed] = useState(false);
  const [ready, setReady] = useState(false);

  if (!enabled) {
    return null;
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setFailed(false);
    setReady(false);
    try {
      const session = await createDemoSession(role);
      window.localStorage.setItem(
        "fruit-agent-access-token",
        session.access_token,
      );
      setReady(true);
      window.dispatchEvent(new Event("fruit-agent-session-changed"));
    } catch {
      setFailed(true);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="demo-entry" aria-labelledby="demo-entry-title">
      <span className="demo-badge">本地虚构数据</span>
      <h2 id="demo-entry-title">进入完整功能演示</h2>
      <p>
        选择一个固定演示角色。页面会调用真实 API 和 PostgreSQL 数据，
        不连接真实店铺，也不会执行退款、改价或发布。
      </p>
      <form onSubmit={submit}>
        <label htmlFor="demo-role">演示角色</label>
        <select
          id="demo-role"
          value={role}
          onChange={(event) => setRole(event.target.value as DemoRole)}
        >
          {Object.entries(roleLabels).map(([value, label]) => (
            <option value={value} key={value}>
              {label}
            </option>
          ))}
        </select>
        <button className="primary-button compact-button" disabled={submitting}>
          {submitting
            ? "正在建立演示会话…"
            : failed
              ? "重新进入演示"
              : "进入完整演示"}
        </button>
      </form>
      {failed ? (
        <p className="error-text" role="alert">
          暂时无法建立演示会话，请确认后端和演示数据已经启动。
        </p>
      ) : null}
      {ready ? <p className="inline-status">演示会话已建立</p> : null}
    </section>
  );
}
