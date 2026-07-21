import { render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";

import { AppShell } from "@/components/app-shell";
import { getSession } from "@/lib/api";

vi.mock("next/navigation", () => ({
  usePathname: () => "/copilot",
}));

vi.mock("@/lib/api", () => ({
  getSession: vi.fn(),
}));

beforeEach(() => {
  localStorage.clear();
  vi.clearAllMocks();
});

it('marks only the active navigation link with aria-current="page"', () => {
  render(
    <AppShell>
      <p>当前页面</p>
    </AppShell>,
  );

  const navigation = screen.getByRole("navigation", { name: "主导航" });
  const links = within(navigation).getAllByRole("link");
  expect(
    within(navigation).getByRole("link", { name: "客服 Copilot" }),
  ).toHaveAttribute("aria-current", "page");
  expect(
    links.filter((link) => link.hasAttribute("aria-current")),
  ).toHaveLength(1);
});

it("shows the active demo identity from the real session endpoint", async () => {
  localStorage.setItem("fruit-agent-access-token", "demo-token");
  vi.mocked(getSession).mockResolvedValue({
    user_id: "10000000-0000-4000-8000-000000000012",
    tenant_id: "10000000-0000-4000-8000-000000000001",
    role: "operator",
    permissions: ["copilot:use"],
  });

  render(
    <AppShell>
      <p>当前页面</p>
    </AppShell>,
  );

  await waitFor(() => expect(getSession).toHaveBeenCalledOnce());
  expect(screen.getByText("当前租户：果序生鲜（华东）")).toBeInTheDocument();
  expect(screen.getByText("运营人员 · 运营支持")).toBeInTheDocument();
});
