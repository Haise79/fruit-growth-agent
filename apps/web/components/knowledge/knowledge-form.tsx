"use client";

import { useState } from "react";

import type {
  KnowledgeItemCreate,
  KnowledgeType,
} from "@/lib/types";

type KnowledgeFormProps = {
  isSaving: boolean;
  onSave: (item: KnowledgeItemCreate) => Promise<void>;
};

const knowledgeTypes: Array<{ value: KnowledgeType; label: string }> = [
  { value: "faq", label: "FAQ" },
  { value: "talking_point", label: "客服话术" },
  { value: "origin_story", label: "产地故事" },
  { value: "product_fact", label: "商品事实" },
  { value: "inventory_fact", label: "库存事实" },
  { value: "price_fact", label: "价格事实" },
];

export function KnowledgeForm({ isSaving, onSave }: KnowledgeFormProps) {
  const [knowledgeType, setKnowledgeType] = useState<KnowledgeType>("faq");
  const [content, setContent] = useState("");
  const [sourceName, setSourceName] = useState("");
  const [responsibleUserId, setResponsibleUserId] = useState("");
  const [validUntil, setValidUntil] = useState("");
  const [error, setError] = useState("");

  async function submit() {
    if (
      !content.trim() ||
      !sourceName.trim() ||
      !responsibleUserId.trim() ||
      !validUntil
    ) {
      setError("请完整填写知识内容、来源、责任人和有效期");
      return;
    }
    setError("");
    await onSave({
      knowledge_type: knowledgeType,
      content: content.trim(),
      source_name: sourceName.trim(),
      responsible_user_id: responsibleUserId.trim(),
      valid_until: validUntil,
    });
  }

  return (
    <section className="knowledge-form" aria-labelledby="knowledge-form-title">
      <h2 id="knowledge-form-title">新增知识</h2>
      <div className="knowledge-form-grid">
        <label>
          <span>知识类型</span>
          <select
            onChange={(event) =>
              setKnowledgeType(event.target.value as KnowledgeType)
            }
            value={knowledgeType}
          >
            {knowledgeTypes.map((type) => (
              <option key={type.value} value={type.value}>
                {type.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>来源名称</span>
          <input
            onChange={(event) => setSourceName(event.target.value)}
            value={sourceName}
          />
        </label>
        <label>
          <span>责任人 ID</span>
          <input
            onChange={(event) => setResponsibleUserId(event.target.value)}
            value={responsibleUserId}
          />
        </label>
        <label>
          <span>有效期</span>
          <input
            onChange={(event) => setValidUntil(event.target.value)}
            type="datetime-local"
            value={validUntil}
          />
        </label>
        <label className="knowledge-content-field">
          <span>知识内容</span>
          <textarea
            onChange={(event) => setContent(event.target.value)}
            rows={4}
            value={content}
          />
        </label>
      </div>
      {error ? (
        <p className="form-error" role="alert">
          {error}
        </p>
      ) : null}
      <button
        className="primary-button compact-button"
        disabled={isSaving}
        onClick={submit}
        type="button"
      >
        {isSaving ? "正在保存…" : "保存新知识"}
      </button>
    </section>
  );
}
