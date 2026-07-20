"use client";

import { useRef, useState } from "react";

import {
  editCopilotSuggestion,
  recordCopilotOutcome,
} from "@/lib/api";
import type {
  CopilotOutcomeEvent,
  CopilotSuggestion,
} from "@/lib/types";

type SuggestionCardProps = {
  caseId: string;
  suggestion: CopilotSuggestion;
  onOutcome: (event: CopilotOutcomeEvent) => Promise<void>;
};

export function SuggestionCard({
  caseId,
  suggestion,
  onOutcome,
}: SuggestionCardProps) {
  const [text, setText] = useState(
    suggestion.edited_text ?? suggestion.original_text,
  );
  const [savedText, setSavedText] = useState(
    suggestion.edited_text ?? suggestion.original_text,
  );
  const [saveStatus, setSaveStatus] = useState("");
  const [adoptStatus, setAdoptStatus] = useState("");
  const [adoptError, setAdoptError] = useState<"copy" | "event" | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [isAdopting, setIsAdopting] = useState(false);
  const adoptionKey = useRef<string | null>(null);
  const isDirty = text !== savedText;

  function getAdoptionKey() {
    if (adoptionKey.current) return adoptionKey.current;

    adoptionKey.current =
      `copilot:${caseId}:suggestion_adopted:${suggestion.id}:${crypto.randomUUID()}`;
    return adoptionKey.current;
  }

  async function saveEdit() {
    const editedText = text.trim();
    if (!editedText) {
      setSaveStatus("建议内容不能为空");
      return;
    }
    setIsSaving(true);
    setSaveStatus("");
    try {
      const saved = await editCopilotSuggestion(
        caseId,
        suggestion.id,
        editedText,
      );
      const persistedText = saved.edited_text ?? saved.original_text;
      setText(persistedText);
      setSavedText(persistedText);
      setSaveStatus("修改已保存");
    } catch {
      setSaveStatus("修改保存失败，请重试");
    } finally {
      setIsSaving(false);
    }
  }

  async function adopt() {
    setIsAdopting(true);
    setAdoptStatus("");
    setAdoptError(null);
    const idempotencyKey = getAdoptionKey();
    try {
      if (!navigator.clipboard?.writeText) {
        throw new Error("clipboard unavailable");
      }
      await navigator.clipboard.writeText(text);
    } catch {
      setAdoptError("copy");
      setAdoptStatus("复制失败，请允许剪贴板访问后重试");
      setIsAdopting(false);
      return;
    }

    try {
      const event = await recordCopilotOutcome(
        caseId,
        {
          event_type: "suggestion_adopted",
          suggestion_id: suggestion.id,
        },
        idempotencyKey,
      );
      adoptionKey.current = null;
      await onOutcome(event);
      setAdoptStatus("已复制并记录采纳");
    } catch {
      setAdoptError("event");
      setAdoptStatus("采纳记录失败，请重试");
    } finally {
      setIsAdopting(false);
    }
  }

  return (
    <article
      aria-label={`建议 ${suggestion.rank}`}
      className="suggestion-row"
    >
      <div className="suggestion-index" aria-hidden="true">
        {suggestion.rank}
      </div>
      <div className="suggestion-main">
        <div className="suggestion-meta">
          <strong>
            {suggestion.recommended_sku_code ?? "未指定推荐 SKU"}
          </strong>
          <span>置信度 {(suggestion.confidence * 100).toFixed(0)}%</span>
          {suggestion.degraded ? <span>降级建议</span> : null}
        </div>
        <label className="visually-hidden" htmlFor={`suggestion-${suggestion.id}`}>
          建议 {suggestion.rank} 内容
        </label>
        <textarea
          id={`suggestion-${suggestion.id}`}
          onChange={(event) => setText(event.target.value)}
          rows={4}
          value={text}
        />
        {suggestion.risk_tip ? (
          <p className="risk-tip">
            <strong>风险提示：</strong>
            {suggestion.risk_tip}
          </p>
        ) : null}
        <div className="citation-list">
          {suggestion.citations.map((citation) => (
            <details key={citation.id}>
              <summary>{citation.source_name}</summary>
              <dl>
                <div>
                  <dt>类型</dt>
                  <dd>{citation.citation_type}</dd>
                </div>
                <div>
                  <dt>来源 ID</dt>
                  <dd>{citation.source_id}</dd>
                </div>
                {Object.entries(citation.snapshot).map(([key, value]) => (
                  <div key={key}>
                    <dt>{key}</dt>
                    <dd>{formatSnapshotValue(value)}</dd>
                  </div>
                ))}
              </dl>
            </details>
          ))}
        </div>
        <div className="suggestion-actions">
          <button
            className="secondary-button"
            disabled={isSaving}
            onClick={saveEdit}
            type="button"
          >
            {isSaving ? "正在保存…" : "保存修改"}
          </button>
          <button
            className="primary-button compact-button"
            disabled={isAdopting || isDirty}
            onClick={adopt}
            type="button"
          >
            {isAdopting
              ? "正在处理…"
              : adoptError
                ? "重试采纳并复制"
                : "采纳并复制"}
          </button>
        </div>
        {isDirty ? (
          <p className="inline-status">请先保存修改，再采纳并复制</p>
        ) : null}
        {saveStatus ? (
          <p
            className={saveStatus.includes("失败") ? "form-error" : "inline-status"}
            role={saveStatus.includes("失败") ? "alert" : "status"}
          >
            {saveStatus}
          </p>
        ) : null}
        {adoptStatus ? (
          <p
            className={adoptError ? "form-error" : "inline-status"}
            role={adoptError ? "alert" : "status"}
          >
            {adoptStatus}
          </p>
        ) : null}
      </div>
    </article>
  );
}

function formatSnapshotValue(value: unknown): string {
  if (typeof value === "string" || typeof value === "number") {
    return String(value);
  }
  return JSON.stringify(value);
}
