import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";

import { KnowledgeWorkspace } from "@/components/knowledge/knowledge-workspace";
import { KnowledgeTable } from "@/components/knowledge/knowledge-table";

const KNOWLEDGE_ID = "11111111-1111-4111-8111-111111111111";
const OWNER_ID = "22222222-2222-4222-8222-222222222222";

function sessionWith(permissions: string[], role = "owner") {
  return {
    user_id: OWNER_ID,
    tenant_id: "33333333-3333-4333-8333-333333333333",
    role,
    permissions,
  };
}

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
  vi.useRealTimers();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

it("fails closed while support permissions are loading and after they resolve", async () => {
  let resolveSession: ((response: Response) => void) | undefined;
  const pendingSession = new Promise<Response>((resolve) => {
    resolveSession = resolve;
  });
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/v1/session")) return pendingSession;
      if (url.endsWith("/api/v1/knowledge/items")) {
        return jsonResponse([knowledgeItem()]);
      }
      throw new Error(`Unexpected request: GET ${url}`);
    }),
  );

  render(<KnowledgeWorkspace />);
  const row = await screen.findByRole("row", { name: /果园客服手册/ });
  expect(screen.queryByRole("button", { name: "新增知识" })).not.toBeInTheDocument();
  expect(within(row).queryByRole("button", { name: "编辑" })).not.toBeInTheDocument();
  expect(within(row).queryByRole("button", { name: "批准" })).not.toBeInTheDocument();

  resolveSession?.(
    new Response(
      JSON.stringify(sessionWith(["knowledge:read"], "support")),
      { status: 200, headers: { "Content-Type": "application/json" } },
    ),
  );
  await waitFor(() =>
    expect(screen.queryByRole("button", { name: "新增知识" })).not.toBeInTheDocument(),
  );
  expect(within(row).queryByRole("button", { name: "编辑" })).not.toBeInTheDocument();
  expect(within(row).queryByRole("button", { name: "批准" })).not.toBeInTheDocument();
});

it("fails closed on session errors and offers a retry", async () => {
  let sessionAttempts = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/v1/session")) {
        sessionAttempts += 1;
        return sessionAttempts === 1
          ? jsonResponse({ detail: "unavailable" }, 503)
          : jsonResponse(
              sessionWith(["knowledge:write", "knowledge:review"], "owner"),
            );
      }
      if (url.endsWith("/api/v1/knowledge/items")) {
        return jsonResponse([knowledgeItem()]);
      }
      throw new Error(`Unexpected request: GET ${url}`);
    }),
  );

  render(<KnowledgeWorkspace />);
  const row = await screen.findByRole("row", { name: /果园客服手册/ });
  expect(await screen.findByText("权限加载失败，请重试")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "重试加载权限" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "新增知识" })).not.toBeInTheDocument();
  expect(within(row).queryByRole("button", { name: "编辑" })).not.toBeInTheDocument();
  expect(within(row).queryByRole("button", { name: "批准" })).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "重试加载权限" }));
  expect(await screen.findByRole("button", { name: "新增知识" })).toBeInTheDocument();
  expect(sessionAttempts).toBe(2);
});

it.each([
  ["owner", ["knowledge:write", "knowledge:review"]],
  ["implementer", ["knowledge:write", "knowledge:review"]],
])("shows maintenance controls only after %s permissions load", async (role, permissions) => {
  let resolveSession: ((response: Response) => void) | undefined;
  const pendingSession = new Promise<Response>((resolve) => {
    resolveSession = resolve;
  });
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/v1/session")) {
        return pendingSession;
      }
      if (url.endsWith("/api/v1/knowledge/items")) {
        return jsonResponse([knowledgeItem()]);
      }
      throw new Error(`Unexpected request: GET ${url}`);
    }),
  );

  render(<KnowledgeWorkspace />);
  const initialRow = await screen.findByRole("row", { name: /果园客服手册/ });
  expect(screen.queryByRole("button", { name: "新增知识" })).not.toBeInTheDocument();
  expect(within(initialRow).queryByRole("button", { name: "编辑" })).not.toBeInTheDocument();
  resolveSession?.(
    new Response(JSON.stringify(sessionWith(permissions, role)), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }),
  );
  expect(await screen.findByRole("button", { name: "新增知识" })).toBeInTheDocument();
  const row = screen.getByRole("row", { name: /果园客服手册/ });
  expect(within(row).getByRole("button", { name: "编辑" })).toBeInTheDocument();
  expect(within(row).getByRole("button", { name: "批准" })).toBeInTheDocument();
  expect(within(row).getByRole("button", { name: "拒绝" })).toBeInTheDocument();
});

it("hides maintenance controls using the current session permissions", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/v1/session")) {
        return jsonResponse({
          user_id: OWNER_ID,
          tenant_id: "33333333-3333-4333-8333-333333333333",
          role: "support",
          permissions: ["knowledge:read"],
        });
      }
      if (url.endsWith("/api/v1/knowledge/items")) {
        return jsonResponse([knowledgeItem()]);
      }
      throw new Error(`Unexpected request: GET ${url}`);
    }),
  );
  render(<KnowledgeWorkspace />);
  const row = await screen.findByRole("row", { name: /果园客服手册/ });
  await waitFor(() => {
    expect(screen.queryByRole("button", { name: "新增知识" })).not.toBeInTheDocument();
    expect(within(row).queryByRole("button", { name: "编辑" })).not.toBeInTheDocument();
    expect(within(row).queryByRole("button", { name: "批准" })).not.toBeInTheDocument();
    expect(within(row).queryByRole("button", { name: "拒绝" })).not.toBeInTheDocument();
  });
});

it("shows every conflicting SKU source for human resolution", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/v1/knowledge/items")) return jsonResponse([]);
      if (url.endsWith("/api/v1/session")) {
        return jsonResponse({ permissions: ["knowledge:read"] });
      }
      if (url.endsWith("/api/v1/knowledge/skus/APPLE-001")) {
        return jsonResponse({
          status: "conflict",
          conflict_source_ids: ["source-a", "source-b"],
          requires_human: true,
        });
      }
      throw new Error(`Unexpected request: GET ${url}`);
    }),
  );
  render(<KnowledgeWorkspace />);
  await userEvent.type(screen.getByLabelText("SKU 冲突查询"), "APPLE-001");
  await userEvent.click(screen.getByRole("button", { name: "查询 SKU" }));
  expect(await screen.findByText("source-a")).toBeInTheDocument();
  expect(screen.getByText("source-b")).toBeInTheDocument();
  expect(screen.getByText("需要人工处理")).toBeInTheDocument();
});

it("loads live knowledge rows with provenance, owner, status, freshness, and content", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/v1/session")) {
        return jsonResponse(sessionWith(["knowledge:read"], "support"));
      }
      if (url.endsWith("/api/v1/knowledge/items")) {
        return jsonResponse([knowledgeItem()]);
      }
      throw new Error(`Unexpected request: GET ${url}`);
    }),
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

it("updates freshness when an item expires while the page stays open", () => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date("2029-12-31T23:59:30Z"));
  const { unmount } = render(
    <KnowledgeTable
      items={[knowledgeItem({ valid_until: "2030-01-01T00:00:00Z" })]}
      onEdit={vi.fn().mockResolvedValue(true)}
      onReview={vi.fn().mockResolvedValue(undefined)}
      pendingId={null}
    />,
  );

  expect(screen.getByText("有效")).toBeInTheDocument();
  act(() => {
    vi.advanceTimersByTime(60_000);
  });
  expect(screen.getByText("已过期")).toBeInTheDocument();
  expect(screen.queryByText("有效")).not.toBeInTheDocument();

  unmount();
  expect(vi.getTimerCount()).toBe(0);
});

it("creates knowledge with the exact API wire names", async () => {
  const created = knowledgeItem({
    review_status: "draft",
    content: "冷藏保存，食用前回温。",
  });
  const fetchMock = vi.fn(
    async (input: RequestInfo | URL, init: RequestInit = {}) => {
      const url = String(input);
      if (url.endsWith("/api/v1/session")) {
        return jsonResponse(
          sessionWith(["knowledge:write", "knowledge:review"], "owner"),
        );
      }
      if (url.endsWith("/api/v1/knowledge/items") && init.method === "POST") {
        expect(JSON.parse(String(init.body))).toEqual({
          knowledge_type: "faq",
          content: "冷藏保存，食用前回温。",
          source_name: "客服知识库",
          responsible_user_id: OWNER_ID,
          valid_until: new Date("2030-01-01T00:00").toISOString(),
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
      if (url.endsWith("/api/v1/session")) {
        return jsonResponse(
          sessionWith(["knowledge:write", "knowledge:review"], "owner"),
        );
      }
      if (url.endsWith(`/items/${KNOWLEDGE_ID}`) && init.method === "PATCH") {
        expect(JSON.parse(String(init.body))).toMatchObject({
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

it("edits every lifecycle field and converts API timestamps for datetime-local", async () => {
  const approved = knowledgeItem();
  const updated = knowledgeItem({
    review_status: "draft",
    knowledge_type: "origin_story",
    source_name: "Updated source",
    responsible_user_id: "55555555-5555-4555-8555-555555555555",
    valid_until: "2031-02-03T04:05:00Z",
    content: "Updated lifecycle content.",
  });
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
      const url = String(input);
      if (url.endsWith("/api/v1/session")) {
        return jsonResponse(
          sessionWith(["knowledge:write", "knowledge:review"], "owner"),
        );
      }
      if (url.endsWith(`/items/${KNOWLEDGE_ID}`) && init.method === "PATCH") {
        expect(JSON.parse(String(init.body))).toEqual({
          knowledge_type: "origin_story",
          source_name: "Updated source",
          responsible_user_id: "55555555-5555-4555-8555-555555555555",
          valid_until: new Date("2031-02-03T04:05").toISOString(),
          content: "Updated lifecycle content.",
        });
        return jsonResponse(updated);
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

  expect(within(row).getByRole("combobox")).toHaveValue("faq");
  const textboxes = within(row).getAllByRole("textbox");
  expect(textboxes.some((control) => control.getAttribute("value") === OWNER_ID)).toBe(
    true,
  );

  await userEvent.selectOptions(within(row).getByRole("combobox"), "origin_story");
  const source = within(row).getByDisplayValue("果园客服手册");
  const owner = within(row).getByDisplayValue(OWNER_ID);
  const validity = within(row).getByDisplayValue(
    localDateTimeValue("2030-01-01T00:00:00Z"),
  );
  const content = within(row).getByRole("textbox", {
    name: "编辑知识内容",
  });
  await userEvent.clear(source);
  await userEvent.type(source, "Updated source");
  await userEvent.clear(owner);
  await userEvent.type(owner, "55555555-5555-4555-8555-555555555555");
  await userEvent.clear(validity);
  await userEvent.type(validity, "2031-02-03T04:05");
  await userEvent.clear(content);
  await userEvent.type(content, "Updated lifecycle content.");
  await userEvent.click(within(row).getByRole("button", { name: "保存编辑" }));

  expect(
    await screen.findByText("Updated lifecycle content."),
  ).toBeInTheDocument();
  expect(screen.getByText("草稿")).toBeInTheDocument();
});

it("round-trips a non-UTC API validity instant through datetime-local", async () => {
  const apiValue = "2030-01-01T12:00:00+08:00";
  const approved = knowledgeItem({ valid_until: apiValue });
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
      const url = String(input);
      if (url.endsWith("/api/v1/session")) {
        return jsonResponse(
          sessionWith(["knowledge:write", "knowledge:review"], "owner"),
        );
      }
      if (url.endsWith(`/items/${KNOWLEDGE_ID}`) && init.method === "PATCH") {
        expect(JSON.parse(String(init.body)).valid_until).toBe(
          new Date(apiValue).toISOString(),
        );
        return jsonResponse(
          knowledgeItem({ review_status: "draft", valid_until: apiValue }),
        );
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
  expect(
    within(row).getByDisplayValue(localDateTimeValue(apiValue)),
  ).toBeInTheDocument();
  await userEvent.click(within(row).getByRole("button", { name: "保存编辑" }));

  expect(await screen.findByText("草稿")).toBeInTheDocument();
});

it("keeps a failed edit available for correction and retry", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
      const url = String(input);
      if (url.endsWith("/api/v1/session")) {
        return jsonResponse(
          sessionWith(["knowledge:write", "knowledge:review"], "owner"),
        );
      }
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
      if (url.endsWith("/api/v1/session")) {
        return jsonResponse(
          sessionWith(["knowledge:write", "knowledge:review"], "owner"),
        );
      }
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
  let listAttempt = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/v1/session")) {
        return jsonResponse(sessionWith(["knowledge:read"], "support"));
      }
      if (url.endsWith("/api/v1/knowledge/items")) {
        listAttempt += 1;
        if (listAttempt === 1) {
          return jsonResponse({ detail: "unauthorized" }, 401);
        }
        return jsonResponse([knowledgeItem()]);
      }
      throw new Error(`Unexpected request: GET ${url}`);
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
  expect(listAttempt).toBe(2);
});

function localDateTimeValue(value: string): string {
  const instant = new Date(value);
  return new Date(instant.getTime() - instant.getTimezoneOffset() * 60_000)
    .toISOString()
    .slice(0, 16);
}
