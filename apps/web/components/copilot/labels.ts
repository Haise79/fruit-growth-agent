import type {
  CopilotCaseStatus,
  CopilotIntent,
  CopilotRisk,
  CopilotStage,
} from "@/lib/types";

export const stageLabels: Record<CopilotStage, string> = {
  presale: "售前",
  aftersale: "售后",
  unknown: "未知",
};

export const intentLabels: Record<CopilotIntent, string> = {
  product_info: "商品信息",
  recommendation: "商品推荐",
  gift: "送礼",
  delivery: "配送",
  storage: "保存",
  damage: "破损",
  refund: "退款",
  complaint: "投诉",
  health_safety: "健康与安全",
  other: "其他",
};

export const riskLabels: Record<CopilotRisk, string> = {
  low: "低风险",
  medium: "中风险",
  high: "高风险",
  critical: "严重风险",
};

export const statusLabels: Record<CopilotCaseStatus, string> = {
  suggestions_ready: "建议已就绪",
  handoff_required: "必须转人工",
  degraded: "降级转人工",
  closed: "工单已关闭",
};
