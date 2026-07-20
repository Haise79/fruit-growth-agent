"use client";

import { useState } from "react";

import type {
  KnowledgeItem,
  KnowledgeReviewStatus,
} from "@/lib/types";

const PAGE_LOADED_AT = Date.now();

type KnowledgeTableProps = {
  items: KnowledgeItem[];
  pendingId: string | null;
  onEdit: (knowledgeId: string, content: string) => Promise<boolean>;
  onReview: (
    knowledgeId: string,
    status: Exclude<KnowledgeReviewStatus, "draft">,
  ) => Promise<void>;
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

export function KnowledgeTable({
  items,
  pendingId,
  onEdit,
  onReview,
}: KnowledgeTableProps) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingContent, setEditingContent] = useState("");

  function startEditing(item: KnowledgeItem) {
    setEditingId(item.id);
    setEditingContent(item.content);
  }

  async function saveEditing() {
    if (!editingId) return;
    const saved = await onEdit(editingId, editingContent.trim());
    if (saved) setEditingId(null);
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
              new Date(item.valid_until).getTime() <= PAGE_LOADED_AT;
            const isEditing = editingId === item.id;
            const isPending = pendingId === item.id;
            return (
              <tr key={item.id}>
                <td>{typeLabels[item.knowledge_type]}</td>
                <td>
                  <strong>{item.source_name}</strong>
                  <small>{item.responsible_user_id ?? "未指定责任人"}</small>
                </td>
                <td>
                  <span className={`review-status status-${item.review_status}`}>
                    {reviewLabels[item.review_status]}
                  </span>
                </td>
                <td>{formatDate(item.updated_at)}</td>
                <td className={expired ? "error-text" : ""}>
                  <span>{item.valid_until ? formatDate(item.valid_until) : "无有效期"}</span>
                  <small>{expired ? "已过期" : "有效"}</small>
                </td>
                <td className="knowledge-content-cell">
                  {isEditing ? (
                    <label>
                      <span className="visually-hidden">编辑知识内容</span>
                      <textarea
                        aria-label="编辑知识内容"
                        onChange={(event) =>
                          setEditingContent(event.target.value)
                        }
                        rows={4}
                        value={editingContent}
                      />
                    </label>
                  ) : (
                    item.content
                  )}
                </td>
                <td>
                  <div className="table-actions">
                    {isEditing ? (
                      <>
                        <button
                          className="text-button"
                          disabled={isPending || !editingContent.trim()}
                          onClick={saveEditing}
                          type="button"
                        >
                          保存编辑
                        </button>
                        <button
                          className="text-button"
                          onClick={() => setEditingId(null)}
                          type="button"
                        >
                          取消
                        </button>
                      </>
                    ) : (
                      <button
                        className="text-button"
                        disabled={isPending}
                        onClick={() => startEditing(item)}
                        type="button"
                      >
                        编辑
                      </button>
                    )}
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

function formatDate(value: string): string {
  return new Date(value).toLocaleString("zh-CN", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}
