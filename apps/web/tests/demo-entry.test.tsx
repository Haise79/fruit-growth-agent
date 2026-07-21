import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";

import { DemoEntry } from "@/components/demo-entry";
import { createDemoSession } from "@/lib/api";
import OverviewPage from "@/app/page";

vi.mock("@/lib/api", () => ({
  createDemoSession: vi.fn(),
}));

beforeEach(() => {
  localStorage.clear();
  vi.clearAllMocks();
});

it("does not expose the demo entry when demo mode is disabled", () => {
  const { container } = render(<DemoEntry enabled={false} />);

  expect(container).toBeEmptyDOMElement();
});

it("enters the real workspace with the selected demo role", async () => {
  vi.mocked(createDemoSession).mockResolvedValue({
    access_token: "short-lived-token",
    role: "operator",
    expires_at: "2026-07-21T12:30:00Z",
  });
  const user = userEvent.setup();
  render(<DemoEntry enabled />);

  await user.selectOptions(screen.getByLabelText("演示角色"), "operator");
  await user.click(screen.getByRole("button", { name: "进入完整演示" }));

  expect(createDemoSession).toHaveBeenCalledWith("operator");
  expect(localStorage.getItem("fruit-agent-access-token")).toBe(
    "short-lived-token",
  );
  expect(screen.getByText("演示会话已建立")).toBeInTheDocument();
});

it("keeps a failed session request visible and retryable", async () => {
  vi.mocked(createDemoSession)
    .mockRejectedValueOnce(new Error("offline"))
    .mockResolvedValueOnce({
      access_token: "retry-token",
      role: "support",
      expires_at: "2026-07-21T12:30:00Z",
    });
  const user = userEvent.setup();
  render(<DemoEntry enabled />);

  await user.selectOptions(screen.getByLabelText("演示角色"), "support");
  await user.click(screen.getByRole("button", { name: "进入完整演示" }));

  expect(screen.getByRole("alert")).toHaveTextContent(
    "暂时无法建立演示会话，请确认后端和演示数据已经启动。",
  );
  await user.click(screen.getByRole("button", { name: "重新进入演示" }));

  expect(createDemoSession).toHaveBeenCalledTimes(2);
  expect(localStorage.getItem("fruit-agent-access-token")).toBe("retry-token");
});

it("shows the complete six-step walkthrough when demo mode is enabled", () => {
  process.env.NEXT_PUBLIC_DEMO_MODE = "true";

  render(<OverviewPage />);

  expect(screen.getByRole("heading", { name: "完整功能演示" })).toBeInTheDocument();
  expect(screen.getAllByRole("listitem")).toHaveLength(6);
  expect(screen.getByText("1. 切换角色与权限")).toBeInTheDocument();
  expect(screen.getByText("6. 查看业务结果闭环")).toBeInTheDocument();
  delete process.env.NEXT_PUBLIC_DEMO_MODE;
});
