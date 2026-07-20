import { render, screen, within } from "@testing-library/react";
import { expect, it, vi } from "vitest";

import { AppShell } from "@/components/app-shell";

vi.mock("next/navigation", () => ({
  usePathname: () => "/copilot",
}));

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
