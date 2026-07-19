const members = [
  ["林果", "owner", "active"],
  ["周岚", "operator", "active"],
  ["陈禾", "support", "active"],
  ["顾行", "implementer", "invited"],
];

export default function MembersPage() {
  return (
    <div className="page">
      <h1>成员权限</h1>
      <p className="page-lead">角色权限为服务端封闭矩阵，前端不可扩权。</p>
      <div className="table-wrap">
        <table>
          <thead>
            <tr><th>成员</th><th>角色</th><th>状态</th></tr>
          </thead>
          <tbody>
            {members.map((member) => (
              <tr key={member[0]}>
                <td>{member[0]}</td><td>{member[1]}</td><td>{member[2]}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
