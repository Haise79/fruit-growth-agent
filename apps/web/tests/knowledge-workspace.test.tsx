import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";

import { KnowledgeWorkspace } from "@/components/knowledge/knowledge-workspace";

const KNOWLEDGE_ID = "11111111-1111-4111-8111-111111111111";
const OWNER_ID = "22222222-2222-4222-8222-222222222222";

function jsonResponse(body: unknown, status = 200) {
  return Promise.resolve(
    new Response(JSON.stringify(body), {
      headers: { "Content-Type": "application/json" },
      status,
    }),
  );
}

function knowledgeItem(overrides: Record<string, unknown> = {}) {
  return {
    id: KNOWLEDGE_ID,
    tenant_id: "33333333-3333-4333-8333-333333333333",
    knowledge_type: "faq",
    review_status: "approved",
    content: "红富士苹果冷藏可保持更好的脆度。",
    source_id: "44444444-4444-4444-8444-444444444444",
    source_name: "果园客服手册",
    responsible_user_id: OWNER_ID,
    valid_until: "2030-01-01T00:00:00Z",
    created_at: "2026-07-20T08:00:00Z",
    updated_at: "2026-07-20T08:00:00Z",
    ...overrides,
  };
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

it("loads live knowledge rows with provenance, owner, status, freshness, and content", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(jsonResponse([knowledgeItem()])),
  );

  render(<KnowledgeWorkspace />);
  expect(screen.getByRole("status")).toHaveTextContent("正在加载知识");

  const row = await screen.findByRole("row", { name: /果园客服手册/ });
  expect(within(row).getByText("FAQ")).toBeInTheDocument();
  expect(within(row).getByText("果园客服手册")).toBeInTheDocument();
  expect(within(row).getByText(OWNER_ID)).toBeInTheDocument();
  expect(within(row).getByText("已审核")).toBeInTheDocument();
  expect(within(row).getByText("有效")).toBeInTheDocument();
  expect(
    within(row).getByText("红富士苹果冷藏可保持更好的脆度。"),
  ).toBeInTheDocument();
  expect(within(row).getByText(/2026/)).toBeInTheDocument();
  expect(within(row).getByText(/2030/)).toBeInTheDocument();
});

it("creates knowledge with the exact API wire names", async () => {
  const created = knowledgeItem({
    review_status: "draft",
    content: "冷藏保存，食用前回温。",
  });
  const fetchMock = vi.fn(
    async (input: RequestInfo | URL, init: RequestInit = {}) => {
      const url = String(input);
      if (url.endsWith("/api/v1/knowledge/items") && init.method === "POST") {
        expect(JSON.parse(String(init.body))).toEqual({
          knowledge_type: "faq",
          content: "冷藏保存，食用前回温。",
          source_name: "客服知识库",
          responsible_user_id: OWNER_ID,
          valid_until: "2030-01-01T00:00",
        });
        return jsonResponse(created, 201);
      }
      if (url.endsWith("/api/v1/knowledge/items")) {
        return jsonResponse([]);
      }
      throw new Error(`Unexpected request: ${init.method ?? "GET"} ${url}`);
    },
  );
  vi.stubGlobal("fetch", fetchMock);

  render(<KnowledgeWorkspace />);
  await screen.findByText("暂无知识记录");
  await userEvent.click(screen.getByRole("button", { name: "新增知识" }));
  await userEvent.selectOptions(screen.getByLabelText("知识类型"), "faq");
  await userEvent.type(screen.getByLabelText("知识内容"), "冷藏保存，食用前回温。");
  await userEvent.type(screen.getByLabelText("来源名称"), "客服知识库");
  await userEvent.type(screen.getByLabelText("责任人 ID"), OWNER_ID);
  await userEvent.type(screen.getByLabelText("有效期"), "2030-01-01T00:00");
  await userEvent.click(screen.getByRole("button", { name: "保存新知识" }));

  expect(await screen.findByText("知识已创建，状态为草稿")).toBeInTheDocument();
  expect(screen.getByText("冷藏保存，食用前回温。")).toBeInTheDocument();
});

it("shows the returned draft reset after editing approved content", async () => {
  const approved = knowledgeItem();
  const edited = knowledgeItem({
    review_status: "draft",
    content: "更新后的冷藏说明。",
    updated_at: "2026-07-20T09:00:00Z",
  });
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
      const url = String(input);
      if (url.endsWith(`/items/${KNOWLEDGE_ID}`) && init.method === "PATCH") {
        expect(JSON.parse(String(init.body))).toEqual({
          content: "更新后的冷藏说明。",
        });
        return jsonResponse(edited);
      }
      if (url.endsWith("/api/v1/knowledge/items")) {
        return jsonResponse([approved]);
      }
      throw new Error(`Unexpected request: ${init.method ?? "GET"} ${url}`);
    }),
  );

  render(<KnowledgeWorkspace />);
  const row = await screen.findByRole("row", { name: /果园客服手册/ });
  await userEvent.click(within(row).getByRole("button", { name: "编辑" }));
  const editor = screen.getByLabelText("编辑知识内容");
  await userEvent.clear(editor);
  await userEvent.type(editor, "更新后的冷藏说明。");
  await userEvent.click(screen.getByRole("button", { name: "保存编辑" }));

  expect(
    await screen.findByText("内容已更新；服务器已将审核状态重置为草稿"),
  ).toBeInTheDocument();
  expect(screen.getByText("草稿")).toBeInTheDocument();
  expect(screen.getByText("更新后的冷藏说明。")).toBeInTheDocument();
});

it("keeps a failed edit available for correction and retry", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
      const url = String(input);
      if (url.endsWith(`/items/${KNOWLEDGE_ID}`) && init.method === "PATCH") {
        return jsonResponse({ detail: "forbidden" }, 403);
      }
      if (url.endsWith("/api/v1/knowledge/items")) {
        return jsonResponse([knowledgeItem()]);
      }
      throw new Error(`Unexpected request: ${init.method ?? "GET"} ${url}`);
    }),
  );

  render(<KnowledgeWorkspace />);
  const row = await screen.findByRole("row", { name: /果园客服手册/ });
  await userEvent.click(within(row).getByRole("button", { name: "编辑" }));
  const editor = screen.getByLabelText("编辑知识内容");
  await userEvent.clear(editor);
  await userEvent.type(editor, "待重试的知识内容。");
  await userEvent.click(screen.getByRole("button", { name: "保存编辑" }));

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "知识编辑失败，请检查权限后重试",
  );
  expect(screen.getByLabelText("编辑知识内容")).toHaveValue(
    "待重试的知识内容。",
  );
  expect(screen.getByRole("button", { name: "保存编辑" })).toBeInTheDocument();
});

it("submits approve and reject review decisions while leaving authority to the API", async () => {
  let current = knowledgeItem({ review_status: "draft" });
  const decisions: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
      const url = String(input);
      if (url.endsWith(`/items/${KNOWLEDGE_ID}/review`)) {
        const body = JSON.parse(String(init.body));
        decisions.push(body.review_status);
        current = knowledgeItem({ review_status: body.review_status });
        return jsonResponse(current);
      }
      if (url.endsWith("/api/v1/knowledge/items")) {
        return jsonResponse([current]);
      }
      throw new Error(`Unexpected request: ${init.method ?? "GET"} ${url}`);
    }),
  );

  render(<KnowledgeWorkspace />);
  const row = await screen.findByRole("row", { name: /果园客服手册/ });
  await userEvent.click(within(row).getByRole("button", { name: "批准" }));
  expect(await screen.findByText("审核结果已更新为已审核")).toBeInTheDocument();
  await userEvent.click(
    within(screen.getByRole("row", { name: /果园客服手册/ }))
      .getByRole("button", { name: "拒绝" }),
  );
  expect(await screen.findByText("审核结果已更新为已拒绝")).toBeInTheDocument();
  expect(decisions).toEqual(["approved", "rejected"]);
});

it("announces load failures and retries the list request", async () => {
  let attempt = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => {
      attempt += 1;
      if (attempt === 1) {
        return jsonResponse({ detail: "unauthorized" }, 401);
      }
      return jsonResponse([knowledgeItem()]);
    }),
  );

  render(<KnowledgeWorkspace />);
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "知识加载失败，请检查登录状态后重试",
  );
  await userEvent.click(screen.getByRole("button", { name: "重新加载" }));

  await waitFor(() =>
    expect(screen.getByText("果园客服手册")).toBeInTheDocument(),
  );
  expect(attempt).toBe(2);
});
