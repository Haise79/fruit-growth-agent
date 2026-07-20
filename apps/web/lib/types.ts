export type RowError = {
  row_number: number;
  field: string;
  reason: string;
  suggestion: string;
};

export type ImportResult = {
  total_rows: number;
  imported_rows: number;
  failed_rows: number;
  errors: RowError[];
};

export type Member = {
  id: string;
  email: string;
  role: "owner" | "operator" | "support" | "implementer";
  status: "active" | "invited" | "suspended";
};

export type Approval = {
  id: string;
  action: string;
  status: "pending" | "approved" | "rejected";
  requires_approval: true;
};
