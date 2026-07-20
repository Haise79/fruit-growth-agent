import re

from fruit_agent.copilot.schemas import (
    CopilotIntent,
    CopilotRisk,
    CopilotStage,
    SafetyClassification,
)

_RISK_ORDER = {
    CopilotRisk.low: 0,
    CopilotRisk.medium: 1,
    CopilotRisk.high: 2,
    CopilotRisk.critical: 3,
}

_AFTERSALE_TERMS = (
    "收到",
    "到货",
    "售后",
    "退款",
    "退货",
    "赔偿",
    "投诉",
    "破损",
    "坏了",
    "烂了",
    "发霉",
    "变质",
    "异味",
    "吃完",
    "受伤",
    "住院",
    "腹泻",
    "呕吐",
    "恶心",
    "腹痛",
    "肚子痛",
    "发烧",
    "发热",
    "头晕",
    "皮疹",
    "呼吸困难",
    "arrived",
    "received",
    "refund",
    "compensation",
    "complaint",
    "damaged",
    "spoiled",
    "rotten",
    "injured",
    "hospitalized",
    "after eating",
    "diarrhea",
    "vomiting",
    "nausea",
    "stomach pain",
    "abdominal pain",
    "fever",
    "dizziness",
    "rash",
    "difficulty breathing",
    "throat swelling",
)
_PRESALE_TERMS = (
    "推荐",
    "想买",
    "购买",
    "送礼",
    "礼物",
    "多少钱",
    "可以吃",
    "怎么选",
    "哪款",
    "recommend",
    "want to buy",
    "gift",
    "how much",
    "is it safe",
)

_SEVERE_HEALTH_TERMS = (
    "anaphylactic shock",
    "anaphylaxis",
    "stopped breathing",
    "not breathing",
    "no longer breathing",
    "unconscious",
    "lost consciousness",
    "ambulance",
    "death",
    "died",
    "dead after",
    "severe swelling",
    "collapsed",
    "unresponsive",
    "couldn't breathe",
    "could not breathe",
    "倒地",
    "无反应",
    "过敏性休克",
    "停止呼吸",
    "没有呼吸",
    "无法呼吸",
    "失去意识",
    "昏迷",
    "救护车",
    "死亡",
    "去世",
    "严重肿胀",
)


def _contains_any(message: str, terms: tuple[str, ...]) -> bool:
    lowered = message.casefold()
    return any(term.casefold() in lowered for term in terms)


def _stage(message: str) -> CopilotStage:
    if _contains_any(message, _AFTERSALE_TERMS):
        return CopilotStage.aftersale
    if _contains_any(message, _PRESALE_TERMS):
        return CopilotStage.presale
    return CopilotStage.unknown


def _ordinary_intent(message: str) -> CopilotIntent:
    intent_terms = (
        (
            CopilotIntent.refund,
            ("退款", "退货", "赔偿", "refund", "compensation", "return"),
        ),
        (
            CopilotIntent.complaint,
            ("投诉", "差评", "曝光", "complaint", "report", "expose"),
        ),
        (
            CopilotIntent.damage,
            ("破损", "压坏", "坏了", "烂了", "damaged", "crushed", "rotten"),
        ),
        (
            CopilotIntent.delivery,
            ("发货", "物流", "快递", "配送", "几天到", "delivery", "shipping"),
        ),
        (
            CopilotIntent.storage,
            ("保存", "储存", "冷藏", "保鲜", "store", "storage", "refrigerate"),
        ),
        (CopilotIntent.gift, ("送礼", "礼物", "礼盒", "gift")),
        (
            CopilotIntent.recommendation,
            ("推荐", "怎么选", "哪款", "recommend", "which one"),
        ),
        (
            CopilotIntent.product_info,
            (
                "多少钱",
                "价格",
                "产地",
                "品种",
                "规格",
                "重量",
                "口感",
                "price",
                "origin",
                "variety",
                "weight",
                "taste",
            ),
        ),
    )
    for intent, terms in intent_terms:
        if _contains_any(message, terms):
            return intent
    return CopilotIntent.other


def classify_customer_message(
    message: str,
    *,
    knowledge_conflict: bool = False,
) -> SafetyClassification:
    stage = _stage(message)
    if knowledge_conflict:
        return SafetyClassification(
            stage=stage,
            intent=_ordinary_intent(message),
            risk=CopilotRisk.high,
            requires_handoff=True,
            reasons=["knowledge_conflict"],
        )

    if _contains_any(message, _SEVERE_HEALTH_TERMS):
        return SafetyClassification(
            stage=CopilotStage.aftersale,
            intent=CopilotIntent.health_safety,
            risk=CopilotRisk.critical,
            requires_handoff=True,
            reasons=["severe_health_emergency"],
        )

    if _contains_any(
        message,
        (
            "整批",
            "批量",
            "大批",
            "几十箱",
            "上百箱",
            "fifty boxes",
            "dozens of boxes",
            "hundreds of boxes",
            "entire batch",
            "bulk",
        ),
    ) or (
        _contains_any(
            message,
            (
                "曝光",
                "微博",
                "抖音",
                "媒体",
                "热搜",
                "舆论",
                "media",
                "go viral",
                "public opinion",
                "expose",
            ),
        )
        and _contains_any(
            message,
            ("不处理", "否则", "就要", "我要", "投诉", "unless", "will", "report"),
        )
    ):
        return SafetyClassification(
            stage=stage,
            intent=CopilotIntent.complaint,
            risk=CopilotRisk.high,
            requires_handoff=True,
            reasons=["bulk_spoilage_or_public_opinion"],
        )

    if _contains_any(
        message,
        (
            "市场监管",
            "监管局",
            "消协",
            "卫生监督",
            "食药监",
            "工商局",
            "消费者协会",
            "消费者权益",
            "消费者热线",
            "消费投诉热线",
            "market regulator",
            "consumer protection agency",
            "food regulator",
        ),
    ) or re.search(r"(?<!\d)(?:12315|12345)(?!\d)", message):
        return SafetyClassification(
            stage=stage,
            intent=CopilotIntent.complaint,
            risk=CopilotRisk.critical,
            requires_handoff=True,
            reasons=["regulator_complaint"],
        )

    if _contains_any(
        message,
        (
            "受伤",
            "住院",
            "医药费",
            "人身伤害",
            "急诊",
            "injured",
            "hospitalized",
            "medical bill",
            "personal injury",
            "emergency room",
        ),
    ):
        return SafetyClassification(
            stage=stage,
            intent=CopilotIntent.health_safety,
            risk=CopilotRisk.critical,
            requires_handoff=True,
            reasons=["personal_injury"],
        )

    if _contains_any(
        message,
        (
            "过敏",
            "糖尿病",
            "疾病",
            "孕妇",
            "婴儿",
            "用药",
            "血糖",
            "高血压",
            "哮喘",
            "心脏病",
            "肾病",
            "肝病",
            "慢性病",
            "癌症",
            "肿瘤",
            "免疫系统",
            "痛风",
            "allergy",
            "allergic",
            "diabetes",
            "disease",
            "pregnant",
            "infant",
            "medication",
            "blood sugar",
            "asthma",
            "heart disease",
            "kidney disease",
            "liver disease",
            "chronic illness",
            "immune disorder",
            "cancer",
            "celiac",
            "gout",
        ),
    ):
        return SafetyClassification(
            stage=stage,
            intent=CopilotIntent.health_safety,
            risk=CopilotRisk.critical,
            requires_handoff=True,
            reasons=["health_allergy_or_disease"],
        )

    if _contains_any(
        message,
        (
            "变质",
            "异味",
            "食物中毒",
            "食品安全",
            "吃坏",
            "腐烂",
            "发霉",
            "food poisoning",
            "food safety",
            "spoiled",
            "rotten",
            "moldy",
            "strange smell",
            "腹泻",
            "呕吐",
            "恶心",
            "腹痛",
            "肚子痛",
            "发烧",
            "发热",
            "头晕",
            "皮疹",
            "呼吸困难",
            "喉咙肿",
            "抽搐",
            "便血",
            "diarrhea",
            "vomiting",
            "nausea",
            "stomach pain",
            "abdominal pain",
            "fever",
            "dizziness",
            "dizzy",
            "rash",
            "difficulty breathing",
            "shortness of breath",
            "throat swelling",
            "swollen throat",
            "seizure",
            "blood in stool",
        ),
    ):
        return SafetyClassification(
            stage=stage,
            intent=CopilotIntent.health_safety,
            risk=CopilotRisk.critical,
            requires_handoff=True,
            reasons=["food_safety"],
        )

    if _contains_any(
        message,
        ("退款", "赔偿", "refund", "compensation"),
    ) and _contains_any(
        message,
        (
            "不同意",
            "超出政策",
            "超过政策",
            "加倍",
            "十倍",
            "三倍",
            "必须赔",
            "拒绝",
            "争议",
            "reject",
            "above policy",
            "beyond policy",
            "demand",
            "dispute",
        ),
    ):
        return SafetyClassification(
            stage=stage,
            intent=CopilotIntent.refund,
            risk=CopilotRisk.high,
            requires_handoff=True,
            reasons=["over_policy_refund_or_compensation"],
        )

    return SafetyClassification(
        stage=stage,
        intent=_ordinary_intent(message),
        risk=CopilotRisk.low,
        requires_handoff=False,
        reasons=[],
    )


def merge_model_risk(
    rule_risk: CopilotRisk,
    model_risk: CopilotRisk,
) -> CopilotRisk:
    if _RISK_ORDER[model_risk] > _RISK_ORDER[rule_risk]:
        return model_risk
    return rule_risk


def merge_safety_classifications(
    raw: SafetyClassification,
    redacted: SafetyClassification,
) -> SafetyClassification:
    raw_score = _RISK_ORDER[raw.risk]
    redacted_score = _RISK_ORDER[redacted.risk]
    if raw_score > redacted_score:
        selected = raw
    elif redacted_score > raw_score:
        selected = redacted
    elif raw.requires_handoff and not redacted.requires_handoff:
        selected = raw
    else:
        selected = redacted
    return SafetyClassification(
        stage=selected.stage,
        intent=selected.intent,
        risk=selected.risk,
        requires_handoff=raw.requires_handoff or redacted.requires_handoff,
        reasons=list(dict.fromkeys([*raw.reasons, *redacted.reasons])),
    )
