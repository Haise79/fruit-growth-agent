const facts = [
  ["APPLE-001", "红富士苹果", "有效", "2030-01-01"],
  ["PEAR-002", "秋月梨", "已过期", "2026-07-01"],
  ["FAQ-018", "水果保存方法", "已审核", "2030-01-01"],
];

export default function KnowledgePage() {
  return (
    <div className="page">
      <h1>知识与商品</h1>
      <p className="page-lead">价格和库存走精确查询；FAQ 与话术走语义检索。</p>
      <div className="table-wrap">
        <table>
          <thead>
            <tr><th>编号</th><th>名称</th><th>新鲜度</th><th>有效期</th></tr>
          </thead>
          <tbody>
            {facts.map((fact) => (
              <tr key={fact[0]}>
                <td>{fact[0]}</td><td>{fact[1]}</td>
                <td className={fact[2] === "已过期" ? "error-text" : ""}>{fact[2]}</td>
                <td>{fact[3]}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
