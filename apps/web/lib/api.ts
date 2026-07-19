import type { Approval, ImportResult, Member } from "@/lib/types";

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

export function listApprovals(): Promise<Approval[]> {
  return api<Approval[]>("/api/v1/approvals");
}
