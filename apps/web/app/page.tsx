import Link from "next/link";

import { DemoEntry } from "@/components/demo-entry";

const capabilities = [
  ["成员与权限", "4 个封闭角色，所有数据按租户隔离"],
  ["知识与商品", "精确事实与叙事检索分流，过期立即拒绝"],
  ["人工审批", "高风险动作只记录决定，不自动执行"],
];

const demoSteps = [
  ["1. 切换角色与权限", "以运营、审核、客服或管理员身份进入同一租户空间。", "/members"],
  ["2. 导入商品数据", "上传带有正确行和错误行的 CSV，查看逐行校验结果。", "/imports"],
  ["3. 管理知识库", "维护商品事实、服务规则和内容素材，并执行审核。", "/knowledge"],
  ["4. 处理人工审批", "对高风险建议批准或拒绝，保留完整审计轨迹。", "/approvals"],
  ["5. 使用运营 Copilot", "根据客户问题生成带引用、风险分级的候选建议。", "/copilot"],
  ["6. 查看业务结果闭环", "回看建议、反馈、结果事件和租户身份。", "/"],
];

export default function OverviewPage() {
  return (
    <div className="page">
      <h1>基础能力概览</h1>
      <p className="page-lead">
        果序 Agent 已覆盖租户权限、商品导入、知识治理、人工审批和运营建议闭环。
      </p>
      <DemoEntry enabled={process.env.NEXT_PUBLIC_DEMO_MODE === "true"} />
      {process.env.NEXT_PUBLIC_DEMO_MODE === "true" ? (
        <section className="demo-route" aria-labelledby="demo-route-title">
          <div className="section-heading">
            <div>
              <span className="demo-badge">推荐路线 · 约 8 分钟</span>
              <h2 id="demo-route-title">完整功能演示</h2>
              <p>按顺序走完六步，就能看到从数据进入到业务结果的完整闭环。</p>
            </div>
          </div>
          <ol>
            {demoSteps.map(([title, description, href]) => (
              <li key={title}>
                <div>
                  <strong>{title}</strong>
                  <p>{description}</p>
                </div>
                <Link href={href}>打开功能</Link>
              </li>
            ))}
          </ol>
        </section>
      ) : null}
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
