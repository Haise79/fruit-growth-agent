"use client";

import { useState } from "react";

import { importProducts } from "@/lib/api";
import type { ImportResult } from "@/lib/types";

export function CsvImportForm() {
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function submit() {
    if (!file) {
      setError("请先选择 CSV 文件");
      return;
    }
    setError("");
    setIsSubmitting(true);
    try {
      setResult(await importProducts(file));
    } catch {
      setError("导入失败，请检查登录状态或稍后重试");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <section className="import-flow" aria-labelledby="import-title">
      <h1 id="import-title">CSV 商品导入</h1>
      <div className="import-actions">
        <label className="file-control">
          <span>选择 CSV</span>
          <input
            accept=".csv,text/csv"
            aria-label="选择 CSV"
            onChange={(event) =>
              setFile(event.target.files?.item(0) ?? null)
            }
            type="file"
          />
        </label>
        <span className="flow-arrow" aria-hidden="true">
          →
        </span>
        <button
          className="primary-button"
          disabled={isSubmitting}
          onClick={submit}
          type="button"
        >
          {isSubmitting ? "正在导入…" : "校验并导入"}
        </button>
      </div>
      <div className="file-meta" aria-live="polite">
        {file ? `已选择：${file.name}` : "支持 UTF-8 CSV，最大 5 MiB"}
      </div>
      {error ? <p className="form-error">{error}</p> : null}

      {result ? (
        <div className="import-result" aria-live="polite">
          <h2>导入校验结果</h2>
          <div className="summary-rail">
            <div>
              <span>总行数</span>
              <strong>{result.total_rows}</strong>
            </div>
            <div>
              <span>成功</span>
              <strong>{result.imported_rows}</strong>
            </div>
            <div className="failed">
              <span>失败</span>
              <strong>{result.failed_rows}</strong>
            </div>
          </div>
          <h3>错误明细（仅展示失败行）</h3>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>行号</th>
                  <th>字段</th>
                  <th>错误信息</th>
                  <th>修正建议</th>
                </tr>
              </thead>
              <tbody>
                {result.errors.map((rowError, index) => (
                  <tr data-testid="row-error" key={`${rowError.field}-${index}`}>
                    <td>第 {rowError.row_number} 行</td>
                    <td className="error-text">{rowError.field}</td>
                    <td>{rowError.reason}</td>
                    <td>{rowError.suggestion}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
    </section>
  );
}
