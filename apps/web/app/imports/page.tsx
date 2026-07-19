import { CsvImportForm } from "@/components/csv-import-form";

export default function ImportsPage() {
  return (
    <div className="page page-import">
      <CsvImportForm />
      <aside className="approval-guard">
        <h2>导入说明</h2>
        <p>每一行独立校验，合法行入库，失败行逐项返回修正建议。</p>
        <hr />
        <strong>事实保护</strong>
        <p>过期价格或库存不会用于 Agent 推荐。</p>
      </aside>
    </div>
  );
}
