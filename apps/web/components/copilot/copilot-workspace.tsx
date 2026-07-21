"use client";

import { useCallback, useEffect, useState } from "react";

import {
  createCopilotCase,
  getCopilotCase,
  listCopilotCases,
} from "@/lib/api";
import type {
  CopilotCase,
  CopilotCaseCreate,
  CopilotOutcomeEvent,
} from "@/lib/types";

import { CaseForm } from "./case-form";
import { CasePanel } from "./case-panel";
import { statusLabels } from "./labels";

export function CopilotWorkspace() {
  const [cases, setCases] = useState<CopilotCase[]>([]);
  const [currentCase, setCurrentCase] = useState<CopilotCase | null>(null);
  const [events, setEvents] = useState<CopilotOutcomeEvent[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [requestError, setRequestError] = useState("");
  const [recentCasesError, setRecentCasesError] = useState("");
  const [refreshError, setRefreshError] = useState("");

  const refreshCases = useCallback(async () => {
    const latest = await listCopilotCases();
    setCases(latest);
    setCurrentCase((selected) => {
      if (selected) {
        return latest.find((item) => item.id === selected.id) ?? selected;
      }
      return latest[0] ?? null;
    });
  }, []);

  useEffect(() => {
    let active = true;
    listCopilotCases()
      .then((latest) => {
        if (!active) return;
        setCases(latest);
        setCurrentCase(latest[0] ?? null);
      })
      .catch(() => {
        if (active) {
          setRecentCasesError("近期工单加载失败，请稍后重试");
        }
      })
      .finally(() => {
        if (active) setIsLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  async function createCase(request: CopilotCaseCreate) {
    setIsSubmitting(true);
    setRequestError("");
    try {
      const created = await createCopilotCase(request);
      setCurrentCase(created);
      setEvents([]);
      try {
        await refreshCases();
        setRecentCasesError("");
      } catch {
        setRecentCasesError("工单已生成，但近期工单刷新失败");
      }
    } catch {
      setRequestError("生成失败，请稍后重试");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function retryRecentCases() {
    const retryError = recentCasesError.startsWith("工单已生成")
      ? "工单已生成，但近期工单刷新失败"
      : "近期工单加载失败，请稍后重试";
    setIsLoading(true);
    try {
      await refreshCases();
      setRecentCasesError("");
    } catch {
      setRecentCasesError(retryError);
    } finally {
      setIsLoading(false);
    }
  }

  async function handleOutcome(event: CopilotOutcomeEvent) {
    setEvents((current) =>
      current.some((existing) => existing.id === event.id)
        ? current
        : [event, ...current],
    );
    try {
      const [detail] = await Promise.all([
        getCopilotCase(event.case_id),
        refreshCases(),
      ]);
      setCurrentCase(detail);
      setRefreshError("");
    } catch {
      setRefreshError("操作已记录，但工单刷新失败，请重试刷新");
    }
  }

  async function retryRefresh() {
    if (!currentCase) return;

    try {
      const [detail] = await Promise.all([
        getCopilotCase(currentCase.id),
        refreshCases(),
      ]);
      setCurrentCase(detail);
      setRefreshError("");
    } catch {
      setRefreshError("操作已记录，但工单刷新失败，请重试刷新");
    }
  }

  async function selectCase(caseId: string) {
    setRequestError("");
    try {
      setCurrentCase(await getCopilotCase(caseId));
      setEvents([]);
    } catch {
      setRequestError("工单详情加载失败，请重试");
    }
  }

  return (
    <div className="page copilot-page">
      <div className="page-title-row">
        <div>
          <h1>客服 Copilot</h1>
          <p className="page-lead">
            基于已审核且有效的知识生成建议；高风险和证据不足场景强制转人工。
          </p>
        </div>
        <p className="safety-note">仅生成草稿 · 不执行外部动作</p>
      </div>

      <div className="copilot-layout">
        <div className="copilot-primary">
          <CaseForm
            isSubmitting={isSubmitting}
            onSubmit={createCase}
            requestFailed={requestError === "生成失败，请稍后重试"}
          />
          {requestError ? (
            <p className="form-error page-alert" role="alert">
              {requestError}
            </p>
          ) : null}
          {refreshError ? (
            <div className="form-error page-alert" role="alert">
              <span>{refreshError}</span>
              <button className="text-button" onClick={retryRefresh} type="button">
                重新刷新工单
              </button>
            </div>
          ) : null}
          {recentCasesError ? (
            <div className="form-error page-alert" role="alert">
              <span>{recentCasesError}</span>
              <button
                className="text-button"
                onClick={retryRecentCases}
                type="button"
              >
                重新加载近期工单
              </button>
            </div>
          ) : null}
          {currentCase ? (
            <CasePanel
              key={currentCase.id}
              currentCase={currentCase}
              events={events}
              onOutcome={handleOutcome}
            />
          ) : null}
        </div>

        <aside className="recent-cases" aria-labelledby="recent-cases-title">
          <div className="section-heading">
            <div>
              <h2 id="recent-cases-title">近期工单</h2>
              <p>按最近更新时间排列</p>
            </div>
          </div>
          {isLoading ? (
            <p role="status">正在加载近期工单…</p>
          ) : recentCasesError ? null : cases.length ? (
            <ol>
              {cases.map((item) => (
                <li key={item.id}>
                  <button
                    aria-current={currentCase?.id === item.id ? "true" : undefined}
                    onClick={() => selectCase(item.id)}
                    type="button"
                  >
                    <span>{item.message}</span>
                    <small>
                      {statusLabels[item.status]} ·{" "}
                      {new Date(item.updated_at).toLocaleString("zh-CN")}
                    </small>
                  </button>
                </li>
              ))}
            </ol>
          ) : (
            <p>暂无近期工单。</p>
          )}
        </aside>
      </div>
    </div>
  );
}
