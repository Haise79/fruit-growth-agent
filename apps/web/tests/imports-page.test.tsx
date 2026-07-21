import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";

import ImportsPage from "@/app/imports/page";

it("offers the bundled Chinese demo CSV", () => {
  render(<ImportsPage />);

  expect(screen.getByRole("link", { name: "下载演示商品 CSV" })).toHaveAttribute(
    "href",
    "/demo-products.csv",
  );
  expect(screen.getByRole("link", { name: "下载演示商品 CSV" })).toHaveAttribute(
    "download",
    "果序生鲜演示商品.csv",
  );
});
