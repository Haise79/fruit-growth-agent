"use client";

import { useCallback, useEffect, useState } from "react";

import {
  createKnowledgeItem,
  getSkuFact,
  getSession,
  listKnowledgeItems,
  reviewKnowledgeItem,
  updateKnowledgeItem,
} from "@/lib/api";
import type {
  KnowledgeItem,
  KnowledgeItemCreate,
  KnowledgeItemUpdate,
  KnowledgeReviewStatus,
  Session,
  ExactFactResult,
} from "@/lib/types";

import { KnowledgeForm } from "./knowledge-form";
import { KnowledgeTable } from "./knowledge-table";

const reviewLabels: Record<Exclude<KnowledgeReviewStatus, "draft">, string> = {
  approved: "已审核",
  rejected: "已拒绝",
};

export function KnowledgeWorkspace() {
  const [items, setItems] = useState<KnowledgeItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [notice, setNotice] = useState("");
  const [actionError, setActionError] = useState("");
  const [session, setSession] = useState<Session | null>(null);
  const [skuCode, setSkuCode] = useState("");
  const [skuResult, setSkuResult] = useState<ExactFactResult | null>(null);
  const [skuError, setSkuError] = useState("");

  const load = useCallback(async () => {
    setIsLoading(true);
    setLoadError(false);
    try {
      setItems(await listKnowledgeItems());
    } catch {
      setLoadError(true);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    listKnowledgeItems()
      .then((loadedItems) => {
        if (active) setItems(loadedItems);
      })
      .catch(() => {
        if (active) setLoadError(true);
      })
      .finally(() => {
        if (active) setIsLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;
    getSession()
      .then((current) => {
        if (active) setSession(current);
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, []);

  const permissions = Array.isArray(session?.permissions)
    ? session.permissions
    : null;
  const canWrite =
    permissions === null || permissions.includes("knowledge:write");
  const canReview =
    permissions === null || permissions.includes("knowledge:review");

  function replaceItem(next: KnowledgeItem) {
    setItems((current) =>
      current.map((item) => (item.id === next.id ? next : item)),
    );
  }

  async function create(item: KnowledgeItemCreate) {
    setIsCreating(true);
    setActionError("");
    setNotice("");
    try {
      const created = await createKnowledgeItem(item);
      setItems((current) => [created, ...current]);
      setNotice("知识已创建，状态为草稿");
      setShowCreate(false);
    } catch {
      setActionError("知识创建失败，请检查字段和权限后重试");
    } finally {
      setIsCreating(false);
    }
  }

  async function edit(knowledgeId: string, changes: KnowledgeItemUpdate) {
    setPendingId(knowledgeId);
    setActionError("");
    setNotice("");
    try {
      const updated = await updateKnowledgeItem(knowledgeId, changes);
      replaceItem(updated);
      setNotice(
        updated.review_status === "draft"
          ? "内容已更新；服务器已将审核状态重置为草稿"
          : `内容已更新；审核状态为 ${updated.review_status}`,
      );
      return true;
    } catch {
      setActionError("知识编辑失败，请检查权限后重试");
      return false;
    } finally {
      setPendingId(null);
    }
  }

  async function review(
    knowledgeId: string,
    status: Exclude<KnowledgeReviewStatus, "draft">,
  ) {
    setPendingId(knowledgeId);
    setActionError("");
    setNotice("");
    try {
      const updated = await reviewKnowledgeItem(knowledgeId, status);
      replaceItem(updated);
      setNotice(`审核结果已更新为${reviewLabels[status]}`);
    } catch {
      setActionError("审核失败；服务器权限或记录状态不允许此操作");
    } finally {
      setPendingId(null);
    }
  }

  async function lookupSku() {
    const code = skuCode.trim();
    if (!code) return;
    setSkuError("");
    try {
      setSkuResult(await getSkuFact(code));
    } catch {
      setSkuResult(null);
      setSkuError("SKU 查询失败，请重试");
    }
  }

  return (
    <div className="page knowledge-page">
      <div className="page-title-row">
        <div>
          <h1>知识与商品</h1>
          <p className="page-lead">
            价格和库存走精确查询；FAQ 与话术走语义检索。
          </p>
        </div>
        {canWrite ? (
          <button
            className="primary-button compact-button"
            onClick={() => setShowCreate((visible) => !visible)}
            type="button"
          >
            {showCreate ? "收起新增" : "新增知识"}
          </button>
        ) : null}
      </div>

      {showCreate ? (
        <KnowledgeForm isSaving={isCreating} onSave={create} />
      ) : null}

      <section className="sku-lookup" aria-label="SKU 事实与冲突">
        <label>
          SKU 冲突查询
          <input
            onChange={(event) => setSkuCode(event.target.value)}
            value={skuCode}
          />
        </label>
        <button className="secondary-button" onClick={lookupSku} type="button">
          查询 SKU
        </button>
        {skuResult?.requires_human ? (
          <div className="handoff-notice" role="status">
            <strong>需要人工处理</strong>
            <ul>
              {skuResult.conflict_source_ids.map((sourceId) => (
                <li key={sourceId}>{sourceId}</li>
              ))}
            </ul>
          </div>
        ) : null}
        {skuError ? <p className="form-error" role="alert">{skuError}</p> : null}
      </section>

      {notice ? (
        <p className="decision-notice" role="status">
          {notice}
        </p>
      ) : null}
      {actionError ? (
        <p className="form-error" role="alert">
          {actionError}
        </p>
      ) : null}

      {isLoading ? <p role="status">正在加载知识…</p> : null}
      {loadError ? (
        <div className="load-error">
          <p className="form-error" role="alert">
            知识加载失败，请检查登录状态后重试
          </p>
          <button className="secondary-button" onClick={load} type="button">
            重新加载
          </button>
        </div>
      ) : null}
      {!isLoading && !loadError && items.length === 0 ? (
        <p className="empty-state">暂无知识记录</p>
      ) : null}
      {!isLoading && !loadError && items.length ? (
        <KnowledgeTable
          items={items}
          canReview={canReview}
          canWrite={canWrite}
          onEdit={edit}
          onReview={review}
          pendingId={pendingId}
        />
      ) : null}
    </div>
  );
}
