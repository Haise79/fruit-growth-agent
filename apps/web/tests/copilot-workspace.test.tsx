import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CopilotWorkspace } from "@/components/copilot/copilot-workspace";

const CASE_ID = "11111111-1111-4111-8111-111111111111";
const SUGGESTION_ID = "22222222-2222-4222-8222-222222222222";

function jsonResponse(body: unknown, status = 200) {
  return Promise.resolve(
    new Response(JSON.stringify(body), {
      headers: { "Content-Type": "application/json" },
      status,
    }),
  );
}

function suggestionCase(overrides: Record<string, unknown> = {}) {
  return {
    id: CASE_ID,
    tenant_id: "33333333-3333-4333-8333-333333333333",
    created_by_user_id: "44444444-4444-4444-8444-444444444444",
    message: "想买脆甜的苹果，请推荐",
    selected_sku_codes: ["APPLE-001"],
    stage: "presale",
    intent: "recommendation",
    risk: "low",
    status: "suggestions_ready",
    risk_reasons: [],
    suggestions: [
      {
        id: SUGGESTION_ID,
        original_text: "推荐烟台红富士，口感脆甜。",
        edited_text: null,
        rank: 1,
        recommended_sku_code: "APPLE-001",
        confidence: 0.93,
        risk_tip: "请确认配送地区和到货时间。",
        degraded: false,
        citations: [
          {
            id: "55555555-5555-4555-8555-555555555555",
            citation_type: "sku",
            source_id: "66666666-6666-4666-8666-666666666666",
            source_name: "商品主数据",
            snapshot: {
              sku_code: "APPLE-001",
              name: "红富士苹果",
              origin: "山东烟台",
            },
            created_at: "2026-07-20T08:00:00Z",
          },
        ],
        created_at: "2026-07-20T08:00:00Z",
        updated_at: "2026-07-20T08:00:00Z",
      },
    ],
    created_at: "2026-07-20T08:00:00Z",
    updated_at: "2026-07-20T08:00:00Z",
    ...overrides,
  };
}

function routeFetch(
  handler?: (url: string, init: RequestInit) => Promise<Response> | undefined,
) {
  return vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
    const url = String(input);
    const handled = handler?.(url, init);
    if (handled) {
      return handled;
    }
    if (url.endsWith("/api/v1/copilot/cases") && !init.method) {
      return jsonResponse([]);
    }
    throw new Error(`Unexpected request: ${init.method ?? "GET"} ${url}`);
  });
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("CopilotWorkspace", () => {
  it("creates a case and renders classifications, latency, and at most three suggestions", async () => {
    const created = suggestionCase({
      suggestions: [
        suggestionCase().suggestions[0],
        {
          ...suggestionCase().suggestions[0],
          id: "77777777-7777-4777-8777-777777777777",
          rank: 2,
          original_text: "第二条建议",
        },
        {
          ...suggestionCase().suggestions[0],
          id: "88888888-8888-4888-8888-888888888888",
          rank: 3,
          original_text: "第三条建议",
        },
        {
          ...suggestionCase().suggestions[0],
          id: "99999999-9999-4999-8999-999999999999",
          rank: 4,
          original_text: "不应渲染的第四条建议",
        },
      ],
    });
    const fetchMock = routeFetch((url, init) => {
      if (url.endsWith("/api/v1/copilot/cases") && init.method === "POST") {
        expect(JSON.parse(String(init.body))).toEqual({
          message: "想买脆甜的苹果，请推荐",
          selected_sku_codes: ["APPLE-001"],
        });
        return jsonResponse(created, 201);
      }
      if (url.endsWith("/api/v1/copilot/cases") && !init.method) {
        return jsonResponse([created]);
      }
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<CopilotWorkspace />);
    await userEvent.type(
      screen.getByLabelText("客户消息"),
      "想买脆甜的苹果，请推荐",
    );
    await userEvent.type(screen.getByLabelText("SKU 代码 1"), "APPLE-001");
    expect(
      screen.queryByRole("button", { name: /发送/ }),
    ).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "生成建议" }));

    expect(await screen.findByText("售前")).toBeInTheDocument();
    expect(screen.getByText("商品推荐")).toBeInTheDocument();
    expect(screen.getByText("低风险")).toBeInTheDocument();
    expect(screen.getByText("建议已就绪")).toBeInTheDocument();
    expect(screen.getByText(/毫秒/)).toBeInTheDocument();
    expect(screen.getAllByRole("article", { name: /建议/ })).toHaveLength(3);
    expect(screen.queryByText("不应渲染的第四条建议")).not.toBeInTheDocument();
  });

  it("shows mandatory handoff reasons without suggestions", async () => {
    const handoff = suggestionCase({
      stage: "aftersale",
      intent: "health_safety",
      risk: "critical",
      status: "handoff_required",
      risk_reasons: ["food_safety", "allergic_reaction"],
      suggestions: [],
    });
    vi.stubGlobal(
      "fetch",
      routeFetch((url, init) => {
        if (url.endsWith("/api/v1/copilot/cases") && init.method === "POST") {
          return jsonResponse(handoff, 201);
        }
      }),
    );

    render(<CopilotWorkspace />);
    await userEvent.type(screen.getByLabelText("客户消息"), "吃完苹果过敏了");
    await userEvent.click(screen.getByRole("button", { name: "生成建议" }));

    expect(await screen.findAllByText("必须转人工")).toHaveLength(2);
    expect(screen.getByText(/food_safety/)).toBeInTheDocument();
    expect(screen.queryByRole("article", { name: /建议/ })).not.toBeInTheDocument();
  });

  it("saves edited text with the exact suggestion wire shape", async () => {
    const current = suggestionCase();
    const editedSuggestion = {
      ...current.suggestions[0],
      edited_text: "推荐烟台红富士，脆甜多汁，请先确认配送地区。",
    };
    vi.stubGlobal(
      "fetch",
      routeFetch((url, init) => {
        if (url.endsWith(`/suggestions/${SUGGESTION_ID}`)) {
          expect(init.method).toBe("PATCH");
          expect(JSON.parse(String(init.body))).toEqual({
            edited_text: editedSuggestion.edited_text,
          });
          return jsonResponse(editedSuggestion);
        }
        if (url.endsWith("/api/v1/copilot/cases") && !init.method) {
          return jsonResponse([current]);
        }
      }),
    );

    render(<CopilotWorkspace />);
    const editor = await screen.findByLabelText("建议 1 内容");
    await userEvent.clear(editor);
    await userEvent.type(editor, editedSuggestion.edited_text);
    await userEvent.click(screen.getByRole("button", { name: "保存修改" }));

    expect(await screen.findByText("修改已保存")).toBeInTheDocument();
  });

  it("copies before adoption, retries failures, and reuses the idempotency key", async () => {
    const current = suggestionCase();
    const calls: string[] = [];
    const clipboard = {
      writeText: vi
        .fn()
        .mockImplementationOnce(async () => {
          calls.push("copy-failed");
          throw new Error("permission denied");
        })
        .mockImplementationOnce(async () => {
          calls.push("copy-success");
        }),
    };
    Object.defineProperty(window.navigator, "clipboard", {
      configurable: true,
      value: clipboard,
    });
    const eventHeaders: string[] = [];
    vi.stubGlobal(
      "fetch",
      routeFetch((url, init) => {
        if (url.endsWith("/events") && init.method === "POST") {
          calls.push("event");
          eventHeaders.push(new Headers(init.headers).get("Idempotency-Key") ?? "");
          return jsonResponse({
            id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            case_id: CASE_ID,
            suggestion_id: SUGGESTION_ID,
            event_type: "suggestion_adopted",
            occurred_at: "2026-07-20T08:10:00Z",
            metadata: {},
            created_at: "2026-07-20T08:10:00Z",
            case_status: "suggestions_ready",
          }, 201);
        }
        if (url.endsWith(`/cases/${CASE_ID}`)) {
          return jsonResponse(current);
        }
        if (url.endsWith("/api/v1/copilot/cases") && !init.method) {
          return jsonResponse([current]);
        }
      }),
    );

    render(<CopilotWorkspace />);
    const adopt = await screen.findByRole("button", { name: "采纳并复制" });
    await userEvent.click(adopt);

    expect(await screen.findByText(/复制失败/)).toBeInTheDocument();
    expect(calls).toEqual(["copy-failed"]);
    expect(screen.queryByText("已复制并记录采纳")).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "重试采纳并复制" }));
    expect(await screen.findByText("已复制并记录采纳")).toBeInTheDocument();
    expect(calls).toEqual(["copy-failed", "copy-success", "event"]);
    expect(eventHeaders[0]).toBe(
      `copilot:${CASE_ID}:suggestion_adopted:${SUGGESTION_ID}`,
    );
  });

  it("does not claim adoption when event recording fails and keeps the same retry key", async () => {
    const current = suggestionCase();
    const clipboard = { writeText: vi.fn().mockResolvedValue(undefined) };
    Object.defineProperty(window.navigator, "clipboard", {
      configurable: true,
      value: clipboard,
    });
    const keys: string[] = [];
    let attempt = 0;
    vi.stubGlobal(
      "fetch",
      routeFetch((url, init) => {
        if (url.endsWith("/events") && init.method === "POST") {
          keys.push(new Headers(init.headers).get("Idempotency-Key") ?? "");
          attempt += 1;
          if (attempt === 1) {
            return jsonResponse({ detail: "temporarily unavailable" }, 503);
          }
          return jsonResponse({
            id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            case_id: CASE_ID,
            suggestion_id: SUGGESTION_ID,
            event_type: "suggestion_adopted",
            occurred_at: "2026-07-20T08:10:00Z",
            metadata: {},
            created_at: "2026-07-20T08:10:00Z",
            case_status: "suggestions_ready",
          }, 201);
        }
        if (url.endsWith(`/cases/${CASE_ID}`)) {
          return jsonResponse(current);
        }
        if (url.endsWith("/api/v1/copilot/cases") && !init.method) {
          return jsonResponse([current]);
        }
      }),
    );

    render(<CopilotWorkspace />);
    await userEvent.click(
      await screen.findByRole("button", { name: "采纳并复制" }),
    );
    expect(await screen.findByText(/采纳记录失败/)).toBeInTheDocument();
    expect(screen.queryByText("已复制并记录采纳")).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "重试采纳并复制" }));
    expect(await screen.findByText("已复制并记录采纳")).toBeInTheDocument();
    expect(keys).toHaveLength(2);
    expect(new Set(keys).size).toBe(1);
    expect(clipboard.writeText).toHaveBeenCalledTimes(2);
  });

  it("expands complete citation details on demand", async () => {
    vi.stubGlobal(
      "fetch",
      routeFetch((url, init) => {
        if (url.endsWith("/api/v1/copilot/cases") && !init.method) {
          return jsonResponse([suggestionCase()]);
        }
      }),
    );
    render(<CopilotWorkspace />);

    expect(await screen.findByText("商品主数据")).toBeInTheDocument();
    const details = screen.getByText("商品主数据").closest("details");
    expect(details).not.toHaveAttribute("open");
    await userEvent.click(screen.getByText("商品主数据"));
    expect(details).toHaveAttribute("open");
    expect(screen.getByText("山东烟台")).toBeInTheDocument();
    expect(screen.getByText("sku")).toBeInTheDocument();
  });

  it.each([
    ["payment", "记录付款"],
    ["refund", "记录退款"],
    ["complaint", "记录投诉"],
    ["case_closed", "关闭工单"],
  ])("records the %s outcome and refreshes detail and recent cases", async (eventType, label) => {
    const current = suggestionCase();
    const requests: Array<{ url: string; init: RequestInit }> = [];
    vi.stubGlobal(
      "fetch",
      routeFetch((url, init) => {
        requests.push({ url, init });
        if (url.endsWith("/events") && init.method === "POST") {
          expect(JSON.parse(String(init.body))).toEqual({
            event_type: eventType,
          });
          expect(new Headers(init.headers).get("Idempotency-Key")).toBe(
            `copilot:${CASE_ID}:${eventType}`,
          );
          return jsonResponse({
            id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
            case_id: CASE_ID,
            suggestion_id: null,
            event_type: eventType,
            occurred_at: "2026-07-20T08:20:00Z",
            metadata: {},
            created_at: "2026-07-20T08:20:00Z",
            case_status: eventType === "case_closed" ? "closed" : "suggestions_ready",
          }, 201);
        }
        if (url.endsWith(`/cases/${CASE_ID}`)) {
          return jsonResponse(
            eventType === "case_closed"
              ? suggestionCase({ status: "closed" })
              : current,
          );
        }
        if (url.endsWith("/api/v1/copilot/cases") && !init.method) {
          return jsonResponse([current]);
        }
      }),
    );
    render(<CopilotWorkspace />);

    await userEvent.click(await screen.findByRole("button", { name: label }));

    expect(await screen.findByText(`已记录：${label.replace("记录", "")}`)).toBeInTheDocument();
    expect(
      requests.some(({ url }) => url.endsWith(`/cases/${CASE_ID}`)),
    ).toBe(true);
    expect(
      requests.filter(({ url, init }) =>
        url.endsWith("/api/v1/copilot/cases") && !init.method
      ).length,
    ).toBeGreaterThanOrEqual(2);
    const timeline = screen.getByRole("region", { name: "本次操作记录" });
    expect(within(timeline).getByText(eventType)).toBeInTheDocument();
  });

  it("announces loading and retryable request errors", async () => {
    let resolveList: ((value: Response) => void) | undefined;
    const firstList = new Promise<Response>((resolve) => {
      resolveList = resolve;
    });
    let failed = false;
    vi.stubGlobal(
      "fetch",
      routeFetch((url, init) => {
        if (url.endsWith("/api/v1/copilot/cases") && !init.method && !resolveList) {
          return firstList;
        }
        if (url.endsWith("/api/v1/copilot/cases") && !init.method) {
          return firstList;
        }
        if (url.endsWith("/api/v1/copilot/cases") && init.method === "POST") {
          failed = true;
          return jsonResponse({ detail: "model unavailable" }, 503);
        }
      }),
    );

    render(<CopilotWorkspace />);
    expect(screen.getByRole("status")).toHaveTextContent("正在加载近期工单");
    resolveList?.(new Response(JSON.stringify([]), { status: 200 }));
    await waitFor(() =>
      expect(screen.queryByText("正在加载近期工单")).not.toBeInTheDocument(),
    );
    await userEvent.type(screen.getByLabelText("客户消息"), "请推荐苹果");
    await userEvent.click(screen.getByRole("button", { name: "生成建议" }));

    expect(failed).toBe(true);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "生成失败，请稍后重试",
    );
    expect(screen.getByRole("button", { name: "重新生成" })).toBeInTheDocument();
  });
});
