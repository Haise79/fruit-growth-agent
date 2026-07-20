"use client";

import { useState } from "react";

const initial = [
  { id: "APR-1048", action: "change_inventory", status: "pending" },
  { id: "APR-1047", action: "refund", status: "approved" },
  { id: "APR-1046", action: "publish_douyin", status: "rejected" },
];

export default function ApprovalsPage() {
  const [items, setItems] = useState(initial);
  const [notice, setNotice] = useState("");

  function decide(id: string, status: "approved" | "rejected") {
    setItems((current) =>
      current.map((item) => (item.id === id ? { ...item, status } : item)),
    );
    setNotice("已记录决策，未执行外部动作");
  }

  return (
    <div className="page">
      <h1>人工审批</h1>
      <p className="page-lead">审批只记录决定，不执行外部动作。</p>
      {notice ? <p className="decision-notice">{notice}</p> : null}
      <div className="table-wrap">
        <table>
          <thead>
            <tr><th>审批号</th><th>动作</th><th>状态</th><th>决定</th></tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.id}>
                <td>{item.id}</td><td>{item.action}</td><td>{item.status}</td>
                <td>
                  {item.status === "pending" ? (
                    <div className="decision-actions">
                      <button onClick={() => decide(item.id, "approved")} type="button">批准</button>
                      <button className="reject" onClick={() => decide(item.id, "rejected")} type="button">拒绝</button>
                    </div>
                  ) : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
