import type {
  Approval,
  CopilotCase,
  CopilotCaseCreate,
  CopilotOutcomeEvent,
  CopilotOutcomeEventCreate,
  CopilotSuggestion,
  ImportResult,
  KnowledgeItem,
  KnowledgeItemCreate,
  KnowledgeItemUpdate,
  KnowledgeReviewStatus,
  Member,
  Session,
  ExactFactResult,
} from "@/lib/types";

function accessToken(): string {
  if (typeof window === "undefined") {
    return "";
  }
  return window.localStorage.getItem("fruit-agent-access-token") ?? "";
}

export async function api<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const token = accessToken();
  const headers = new Headers(init?.headers);
  headers.set("X-Request-ID", crypto.randomUUID());
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  const response = await fetch(
    `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}${path}`,
    {
      ...init,
      headers,
      cache: "no-store",
    },
  );
  if (!response.ok) {
    throw await response.json();
  }
  return response.json() as Promise<T>;
}

export function importProducts(file: File): Promise<ImportResult> {
  const body = new FormData();
  body.append("file", file);
  return api<ImportResult>("/api/v1/imports/products", {
    method: "POST",
    body,
  });
}

export function listMembers(): Promise<Member[]> {
  return api<Member[]>("/api/v1/members");
}

export function getSession(): Promise<Session> {
  return api<Session>("/api/v1/session");
}

export function getSkuFact(skuCode: string): Promise<ExactFactResult> {
  return api<ExactFactResult>(
    `/api/v1/knowledge/skus/${encodeURIComponent(skuCode)}`,
  );
}

export function listApprovals(): Promise<Approval[]> {
  return api<Approval[]>("/api/v1/approvals");
}

function jsonInit(method: "POST" | "PATCH", body: unknown): RequestInit {
  return {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
}

export function createCopilotCase(
  body: CopilotCaseCreate,
): Promise<CopilotCase> {
  return api<CopilotCase>(
    "/api/v1/copilot/cases",
    jsonInit("POST", body),
  );
}

export function listCopilotCases(
  limit?: number,
  offset?: number,
): Promise<CopilotCase[]> {
  if (limit === undefined && offset === undefined) {
    return api<CopilotCase[]>("/api/v1/copilot/cases");
  }
  const query = new URLSearchParams({
    limit: String(limit ?? 50),
    offset: String(offset ?? 0),
  });
  return api<CopilotCase[]>(`/api/v1/copilot/cases?${query}`);
}

export function getCopilotCase(caseId: string): Promise<CopilotCase> {
  return api<CopilotCase>(`/api/v1/copilot/cases/${caseId}`);
}

export function editCopilotSuggestion(
  caseId: string,
  suggestionId: string,
  editedText: string,
): Promise<CopilotSuggestion> {
  return api<CopilotSuggestion>(
    `/api/v1/copilot/cases/${caseId}/suggestions/${suggestionId}`,
    jsonInit("PATCH", { edited_text: editedText }),
  );
}

export function recordCopilotOutcome(
  caseId: string,
  body: CopilotOutcomeEventCreate,
  idempotencyKey: string,
): Promise<CopilotOutcomeEvent> {
  return api<CopilotOutcomeEvent>(
    `/api/v1/copilot/cases/${caseId}/events`,
    {
      ...jsonInit("POST", body),
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": idempotencyKey,
      },
    },
  );
}

export function listKnowledgeItems(): Promise<KnowledgeItem[]> {
  return api<KnowledgeItem[]>("/api/v1/knowledge/items");
}

export function createKnowledgeItem(
  body: KnowledgeItemCreate,
): Promise<KnowledgeItem> {
  return api<KnowledgeItem>(
    "/api/v1/knowledge/items",
    jsonInit("POST", body),
  );
}

export function updateKnowledgeItem(
  knowledgeId: string,
  body: KnowledgeItemUpdate,
): Promise<KnowledgeItem> {
  return api<KnowledgeItem>(
    `/api/v1/knowledge/items/${knowledgeId}`,
    jsonInit("PATCH", body),
  );
}

export function reviewKnowledgeItem(
  knowledgeId: string,
  reviewStatus: Exclude<KnowledgeReviewStatus, "draft">,
): Promise<KnowledgeItem> {
  return api<KnowledgeItem>(
    `/api/v1/knowledge/items/${knowledgeId}/review`,
    jsonInit("POST", { review_status: reviewStatus }),
  );
}
