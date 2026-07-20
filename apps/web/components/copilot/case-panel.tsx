"use client";

import { useRef, useState } from "react";

import { recordCopilotOutcome } from "@/lib/api";
import type {
  CopilotCase,
  CopilotOutcomeEvent,
  CopilotOutcomeEventType,
} from "@/lib/types";

import {
  intentLabels,
  riskLabels,
  stageLabels,
  statusLabels,
} from "./labels";
import { SuggestionCard } from "./suggestion-card";

type CasePanelProps = {
  currentCase: CopilotCase;
  latencyMs: number | null;
  events: CopilotOutcomeEvent[];
  onOutcome: (event: CopilotOutcomeEvent) => Promise<void>;
};

const actions: Array<{
  eventType: Exclude<CopilotOutcomeEventType, "suggestion_adopted" | "suggestion_rejected">;
  label: string;
}> = [
  { eventType: "payment", label: "记录付款" },
  { eventType: "refund", label: "记录退款" },
  { eventType: "complaint", label: "记录投诉" },
  { eventType: "case_closed", label: "关闭工单" },
];

export function CasePanel({
  currentCase,
  latencyMs,
  events,
  onOutcome,
}: CasePanelProps) {
  const [actionStatus, setActionStatus] = useState("");
  const [actionError, setActionError] = useState(false);
  const [pendingAction, setPendingAction] =
    useState<CopilotOutcomeEventType | null>(null);
  const actionKeys = useRef<Partial<Record<CopilotOutcomeEventType, string>>>(
    {},
  );

  function getActionKey(eventType: CopilotOutcomeEventType) {
    const existing = actionKeys.current[eventType];
    if (existing) return existing;

    const created = `copilot:${currentCase.id}:${eventType}:${crypto.randomUUID()}`;
    actionKeys.current[eventType] = created;
    return created;
  }

  async function recordAction(
    eventType: Exclude<CopilotOutcomeEventType, "suggestion_adopted" | "suggestion_rejected">,
    label: string,
  ) {
    setPendingAction(eventType);
    setActionStatus("");
    setActionError(false);
    const idempotencyKey = getActionKey(eventType);
    try {
      const event = await recordCopilotOutcome(
        currentCase.id,
        { event_type: eventType },
        idempotencyKey,
      );
      await onOutcome(event);
      delete actionKeys.current[eventType];
      setActionStatus(`已记录：${label.replace("记录", "")}`);
    } catch {
      setActionError(true);
      setActionStatus(`${label}失败，请重试`);
    } finally {
      setPendingAction(null);
    }
  }

  const isHandoff =
    currentCase.status === "handoff_required" ||
    currentCase.status === "degraded";

  return (
    <section className="case-detail" aria-labelledby="case-detail-title">
      <div className="section-heading">
        <div>
          <h2 id="case-detail-title">处理结果</h2>
          <p>工单 {currentCase.id}</p>
        </div>
        {latencyMs !== null ? (
          <span className="latency">{latencyMs} 毫秒</span>
        ) : null}
      </div>

      <dl className="classification-rail">
        <div>
          <dt>阶段</dt>
          <dd>{stageLabels[currentCase.stage]}</dd>
        </div>
        <div>
          <dt>意图</dt>
          <dd>{intentLabels[currentCase.intent]}</dd>
        </div>
        <div>
          <dt>风险</dt>
          <dd className={`risk-${currentCase.risk}`}>
            {riskLabels[currentCase.risk]}
          </dd>
        </div>
        <div>
          <dt>状态</dt>
          <dd>{statusLabels[currentCase.status]}</dd>
        </div>
      </dl>

      {isHandoff ? (
        <div className="handoff-notice" role="status">
          <strong>{statusLabels[currentCase.status]}</strong>
          <p>
            {currentCase.risk_reasons.length
              ? currentCase.risk_reasons.join(" · ")
              : "证据不足或模型暂不可用，请交由人工处理。"}
          </p>
        </div>
      ) : null}

      {currentCase.suggestions.slice(0, 3).map((suggestion) => (
        <SuggestionCard
          caseId={currentCase.id}
          key={suggestion.id}
          onOutcome={onOutcome}
          suggestion={suggestion}
        />
      ))}

      <div className="outcome-strip">
        <h3>结果记录</h3>
        <div className="outcome-actions">
          {actions.map(({ eventType, label }) => (
            <button
              className={eventType === "case_closed" ? "secondary-button" : "text-button"}
              disabled={pendingAction !== null || currentCase.status === "closed"}
              key={eventType}
              onClick={() => recordAction(eventType, label)}
              type="button"
            >
              {pendingAction === eventType ? "正在记录…" : label}
            </button>
          ))}
        </div>
        {actionStatus ? (
          <p
            className={actionError ? "form-error" : "inline-status"}
            role={actionError ? "alert" : "status"}
          >
            {actionStatus}
          </p>
        ) : null}
      </div>

      <section
        aria-label="本次操作记录"
        className="event-timeline"
        role="region"
      >
        <h3>本次操作记录</h3>
        {events.length ? (
          <ol>
            {events.map((event) => (
              <li key={event.id}>
                <strong>{event.event_type}</strong>
                <time dateTime={event.occurred_at}>
                  {new Date(event.occurred_at).toLocaleString("zh-CN")}
                </time>
              </li>
            ))}
          </ol>
        ) : (
          <p>当前页面尚无操作记录。</p>
        )}
      </section>
    </section>
  );
}
