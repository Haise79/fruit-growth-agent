import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";

import { CsvImportForm } from "@/components/csv-import-form";

afterEach(() => {
  vi.restoreAllMocks();
});

it("renders every CSV row error", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          total_rows: 2,
          imported_rows: 1,
          failed_rows: 1,
          errors: [
            {
              row_number: 3,
              field: "price",
              reason: "must be greater than 0",
              suggestion: "输入正数价格",
            },
            {
              row_number: 3,
              field: "inventory",
              reason: "must be an integer",
              suggestion: "输入整数库存",
            },
          ],
        }),
        { status: 200 },
      ),
    ),
  );
  render(<CsvImportForm />);
  const csvFile = new File(["sku_code,name"], "products.csv", {
    type: "text/csv",
  });

  await userEvent.upload(screen.getByLabelText("选择 CSV"), csvFile);
  await userEvent.click(
    screen.getByRole("button", { name: "校验并导入" }),
  );

  expect(await screen.findAllByTestId("row-error")).toHaveLength(2);
});
