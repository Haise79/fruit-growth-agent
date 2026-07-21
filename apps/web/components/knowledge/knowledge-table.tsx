"use client";

import { useEffect, useState } from "react";

import type {
  KnowledgeItem,
  KnowledgeItemUpdate,
  KnowledgeReviewStatus,
  KnowledgeType,
} from "@/lib/types";

type KnowledgeTableProps = {
  items: KnowledgeItem[];
  canWrite?: boolean;
  canReview?: boolean;
  pendingId: string | null;
  onEdit: (
    knowledgeId: string,
    changes: KnowledgeItemUpdate,
  ) => Promise<boolean>;
  onReview: (
    knowledgeId: string,
    status: Exclude<KnowledgeReviewStatus, "draft">,
  ) => Promise<void>;
};

type KnowledgeEditDraft = {
  knowledgeType: KnowledgeType;
  content: string;
  sourceName: string;
  responsibleUserId: string;
  validUntil: string;
};

const typeLabels: Record<KnowledgeItem["knowledge_type"], string> = {
  faq: "FAQ",
  talking_point: "客服话术",
  origin_story: "产地故事",
  product_fact: "商品事实",
  inventory_fact: "库存事实",
  price_fact: "价格事实",
};

const reviewLabels: Record<KnowledgeReviewStatus, string> = {
  draft: "草稿",
  approved: "已审核",
  rejected: "已拒绝",
};

const knowledgeTypes = Object.entries(typeLabels) as Array<
  [KnowledgeType, string]
>;

export function KnowledgeTable({
  items,
  canWrite = true,
  canReview = true,
  pendingId,
  onEdit,
  onReview,
}: KnowledgeTableProps) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draft, setDraft] = useState<KnowledgeEditDraft | null>(null);
  const now = useNow();

  function startEditing(item: KnowledgeItem) {
    setEditingId(item.id);
    setDraft({
      knowledgeType: item.knowledge_type,
      content: item.content,
      sourceName: item.source_name,
      responsibleUserId: item.responsible_user_id ?? "",
      validUntil: item.valid_until ? toDateTimeLocal(item.valid_until) : "",
    });
  }

  function updateDraft(changes: Partial<KnowledgeEditDraft>) {
    setDraft((current) => (current ? { ...current, ...changes } : current));
  }

  async function saveEditing() {
    if (
      !editingId ||
      !draft ||
      !draft.content.trim() ||
      !draft.sourceName.trim() ||
      !draft.responsibleUserId.trim() ||
      !draft.validUntil
    ) {
      return;
    }
    const saved = await onEdit(editingId, {
      knowledge_type: draft.knowledgeType,
      source_name: draft.sourceName.trim(),
      responsible_user_id: draft.responsibleUserId.trim(),
      valid_until: new Date(draft.validUntil).toISOString(),
      content: draft.content.trim(),
    });
    if (saved) {
      setEditingId(null);
      setDraft(null);
    }
  }

  function cancelEditing() {
    setEditingId(null);
    setDraft(null);
  }

  return (
    <div className="table-wrap knowledge-table-wrap">
      <table className="knowledge-table">
        <thead>
          <tr>
            <th>类型</th>
            <th>来源与责任人</th>
            <th>审核状态</th>
            <th>更新时间</th>
            <th>有效期 / 新鲜度</th>
            <th>内容</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => {
            const expired =
              !item.valid_until ||
              new Date(item.valid_until).getTime() <= now;
            const isEditing = editingId === item.id && draft !== null;
            const isPending = pendingId === item.id;
            return (
              <tr key={item.id}>
                <td>
                  {isEditing ? (
                    <label>
                      <span className="visually-hidden">编辑知识类型</span>
                      <select
                        onChange={(event) =>
                          updateDraft({
                            knowledgeType: event.target.value as KnowledgeType,
                          })
                        }
                        value={draft.knowledgeType}
                      >
                        {knowledgeTypes.map(([value, label]) => (
                          <option key={value} value={value}>
                            {label}
                          </option>
                        ))}
                      </select>
                    </label>
                  ) : (
                    typeLabels[item.knowledge_type]
                  )}
                </td>
                <td>
                  {isEditing ? (
                    <>
                      <label>
                        <span className="visually-hidden">编辑来源名称</span>
                        <input
                          onChange={(event) =>
                            updateDraft({ sourceName: event.target.value })
                          }
                          value={draft.sourceName}
                        />
                      </label>
                      <label>
                        <span className="visually-hidden">编辑责任人 ID</span>
                        <input
                          onChange={(event) =>
                            updateDraft({
                              responsibleUserId: event.target.value,
                            })
                          }
                          value={draft.responsibleUserId}
                        />
                      </label>
                    </>
                  ) : (
                    <>
                      <strong>{item.source_name}</strong>
                      <small>
                        {item.responsible_user_id ?? "未指定责任人"}
                      </small>
                    </>
                  )}
                </td>
                <td>
                  <span className={`review-status status-${item.review_status}`}>
                    {reviewLabels[item.review_status]}
                  </span>
                </td>
                <td>{formatDate(item.updated_at)}</td>
                <td className={expired ? "error-text" : ""}>
                  {isEditing ? (
                    <label>
                      <span className="visually-hidden">编辑有效期</span>
                      <input
                        onChange={(event) =>
                          updateDraft({ validUntil: event.target.value })
                        }
                        type="datetime-local"
                        value={draft.validUntil}
                      />
                    </label>
                  ) : (
                    <>
                      <span>
                        {item.valid_until
                          ? formatDate(item.valid_until)
                          : "无有效期"}
                      </span>
                      <small>{expired ? "已过期" : "有效"}</small>
                    </>
                  )}
                </td>
                <td className="knowledge-content-cell">
                  {isEditing ? (
                    <label>
                      <span className="visually-hidden">编辑知识内容</span>
                      <textarea
                        aria-label="编辑知识内容"
                        onChange={(event) =>
                          updateDraft({ content: event.target.value })
                        }
                        rows={4}
                        value={draft.content}
                      />
                    </label>
                  ) : (
                    item.content
                  )}
                </td>
                <td>
                  <div className="table-actions">
                    {canWrite && isEditing ? (
                      <>
                        <button
                          className="text-button"
                          disabled={
                            isPending ||
                            !draft.content.trim() ||
                            !draft.sourceName.trim() ||
                            !draft.responsibleUserId.trim() ||
                            !draft.validUntil
                          }
                          onClick={saveEditing}
                          type="button"
                        >
                          保存编辑
                        </button>
                        <button
                          className="text-button"
                          onClick={cancelEditing}
                          type="button"
                        >
                          取消
                        </button>
                      </>
                    ) : canWrite ? (
                      <button
                        className="text-button"
                        disabled={isPending}
                        onClick={() => startEditing(item)}
                        type="button"
                      >
                        编辑
                      </button>
                    ) : null}
                    {canReview ? (
                      <>
                        <button
                          className="text-button"
                          disabled={isPending}
                          onClick={() => onReview(item.id, "approved")}
                          type="button"
                        >
                          批准
                        </button>
                        <button
                          className="text-button danger-button"
                          disabled={isPending}
                          onClick={() => onReview(item.id, "rejected")}
                          type="button"
                        >
                          拒绝
                        </button>
                      </>
                    ) : null}
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function useNow(intervalMs = 60_000) {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const intervalId = window.setInterval(() => {
      setNow(Date.now());
    }, intervalMs);
    return () => window.clearInterval(intervalId);
  }, [intervalMs]);

  return now;
}

function formatDate(value: string): string {
  return new Date(value).toLocaleString("zh-CN", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function toDateTimeLocal(value: string): string {
  const instant = new Date(value);
  const local = new Date(
    instant.getTime() - instant.getTimezoneOffset() * 60_000,
  );
  return local.toISOString().slice(0, 16);
}
