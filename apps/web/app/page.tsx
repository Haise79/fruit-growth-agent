const capabilities = [
  ["成员与权限", "4 个封闭角色，所有数据按租户隔离"],
  ["知识与商品", "精确事实与叙事检索分流，过期立即拒绝"],
  ["人工审批", "高风险动作只记录决定，不自动执行"],
];

export default function OverviewPage() {
  return (
    <div className="page">
      <h1>基础能力概览</h1>
      <p className="page-lead">
        第 1–2 周基础底座已覆盖租户、审计、知识和人工审批边界。
      </p>
      <div className="overview-list">
        {capabilities.map(([title, description]) => (
          <article key={title}>
            <h2>{title}</h2>
            <p>{description}</p>
          </article>
        ))}
      </div>
    </div>
  );
}
