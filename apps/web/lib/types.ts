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

export type KnowledgeType =
  | "faq"
  | "talking_point"
  | "origin_story"
  | "product_fact"
  | "inventory_fact"
  | "price_fact";

export type KnowledgeReviewStatus = "draft" | "approved" | "rejected";

export type KnowledgeItem = {
  id: string;
  tenant_id: string;
  knowledge_type: KnowledgeType;
  review_status: KnowledgeReviewStatus;
  content: string;
  source_id: string;
  source_name: string;
  responsible_user_id: string | null;
  valid_until: string | null;
  created_at: string;
  updated_at: string;
};

export type KnowledgeItemCreate = {
  knowledge_type: KnowledgeType;
  content: string;
  source_name: string;
  responsible_user_id: string;
  valid_until: string;
};

export type KnowledgeItemUpdate = Partial<KnowledgeItemCreate>;

export type CopilotStage = "presale" | "aftersale" | "unknown";

export type CopilotIntent =
  | "product_info"
  | "recommendation"
  | "gift"
  | "delivery"
  | "storage"
  | "damage"
  | "refund"
  | "complaint"
  | "health_safety"
  | "other";

export type CopilotRisk = "low" | "medium" | "high" | "critical";

export type CopilotCaseStatus =
  | "suggestions_ready"
  | "handoff_required"
  | "degraded"
  | "closed";

export type CopilotCitation = {
  id: string;
  citation_type: "sku" | "knowledge";
  source_id: string;
  source_name: string;
  snapshot: Record<string, unknown>;
  created_at: string;
};

export type CopilotSuggestion = {
  id: string;
  original_text: string;
  edited_text: string | null;
  rank: number;
  recommended_sku_code: string | null;
  confidence: number;
  risk_tip: string | null;
  degraded: boolean;
  citations: CopilotCitation[];
  created_at: string;
  updated_at: string;
};

export type CopilotCase = {
  id: string;
  tenant_id: string;
  created_by_user_id: string;
  message: string;
  selected_sku_codes: string[];
  stage: CopilotStage;
  intent: CopilotIntent;
  risk: CopilotRisk;
  status: CopilotCaseStatus;
  risk_reasons: string[];
  suggestions: CopilotSuggestion[];
  created_at: string;
  updated_at: string;
};

export type CopilotCaseCreate = {
  message: string;
  selected_sku_codes: string[];
};

export type CopilotOutcomeEventType =
  | "suggestion_adopted"
  | "suggestion_rejected"
  | "payment"
  | "refund"
  | "complaint"
  | "case_closed";

export type CopilotOutcomeEventCreate = {
  event_type: CopilotOutcomeEventType;
  suggestion_id?: string;
  occurred_at?: string;
  metadata?: Record<string, unknown>;
};

export type CopilotOutcomeEvent = {
  id: string;
  case_id: string;
  suggestion_id: string | null;
  event_type: CopilotOutcomeEventType;
  occurred_at: string;
  metadata: Record<string, unknown>;
  created_at: string;
  case_status: CopilotCaseStatus;
};
