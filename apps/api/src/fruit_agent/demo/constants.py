from dataclasses import dataclass
from uuid import UUID

from fruit_agent.identity.models import Role

DEMO_TENANT_ID = UUID("10000000-0000-4000-8000-000000000001")

DEMO_USERS: dict[Role, UUID] = {
    Role.owner: UUID("10000000-0000-4000-8000-000000000011"),
    Role.operator: UUID("10000000-0000-4000-8000-000000000012"),
    Role.support: UUID("10000000-0000-4000-8000-000000000013"),
    Role.implementer: UUID("10000000-0000-4000-8000-000000000014"),
}

DEMO_MEMBERSHIPS: dict[Role, UUID] = {
    Role.owner: UUID("10000000-0000-4000-8000-000000000021"),
    Role.operator: UUID("10000000-0000-4000-8000-000000000022"),
    Role.support: UUID("10000000-0000-4000-8000-000000000023"),
    Role.implementer: UUID("10000000-0000-4000-8000-000000000024"),
}

DEMO_SKU_IDS = tuple(
    UUID(f"10000000-0000-4000-8000-00000000003{index}")
    for index in range(1, 7)
)
DEMO_SKU_SOURCE_IDS = tuple(
    UUID(f"10000000-0000-4000-8000-00000000004{index}")
    for index in range(1, 7)
)
DEMO_KNOWLEDGE_IDS = tuple(
    UUID(f"10000000-0000-4000-8000-00000000005{index}")
    for index in range(1, 9)
)
DEMO_KNOWLEDGE_SOURCE_IDS = tuple(
    UUID(f"10000000-0000-4000-8000-00000000006{index}")
    for index in range(1, 9)
)
DEMO_APPROVAL_IDS = tuple(
    UUID(f"10000000-0000-4000-8000-00000000007{index}")
    for index in range(1, 5)
)
DEMO_CASE_IDS = tuple(
    UUID(f"10000000-0000-4000-8000-00000000008{index}")
    for index in range(1, 6)
)
DEMO_SUGGESTION_IDS = (
    UUID("10000000-0000-4000-8000-000000000091"),
    UUID("10000000-0000-4000-8000-000000000092"),
)
DEMO_CITATION_IDS = (
    UUID("10000000-0000-4000-8000-0000000000a1"),
    UUID("10000000-0000-4000-8000-0000000000a2"),
)
DEMO_OUTCOME_IDS = tuple(
    UUID(f"10000000-0000-4000-8000-0000000000b{index}")
    for index in range(1, 6)
)


@dataclass(frozen=True)
class DemoSku:
    sku_code: str
    name: str
    price: str
    inventory: int
    variety: str
    origin: str
    orchard: str
    taste: str
    ripeness: str
    specification: str
    net_weight_grams: int
    sales_regions: tuple[str, ...]
    shipping_eta: str


DEMO_SKUS = (
    DemoSku(
        "YN-APPLE-5",
        "云南昭通丑苹果 5斤装",
        "39.90",
        128,
        "冰糖心",
        "云南昭通",
        "高原合作果园",
        "脆甜微酸",
        "即食",
        "净重 2.5kg",
        2500,
        ("华东", "华南"),
        "下单后 48 小时内发货",
    ),
    DemoSku(
        "FJ-POMELO-2",
        "福建平和红心蜜柚 2枚",
        "49.90",
        64,
        "红肉蜜柚",
        "福建平和",
        "琯溪示范果园",
        "清甜多汁",
        "即食",
        "单果 1.1–1.4kg",
        2400,
        ("华东", "华中"),
        "下单后 24 小时内发货",
    ),
    DemoSku(
        "SC-KIWI-24",
        "四川红心猕猴桃 24枚",
        "59.00",
        92,
        "红阳",
        "四川蒲江",
        "蒲江生态果园",
        "软糯香甜",
        "到货后催熟 2–3 天",
        "24 枚礼盒",
        2200,
        ("华东", "西南"),
        "下单后 48 小时内发货",
    ),
    DemoSku(
        "HN-MANGO-5",
        "海南贵妃芒 5斤装",
        "69.90",
        37,
        "贵妃芒",
        "海南三亚",
        "崖州芒果基地",
        "浓甜带果香",
        "七成熟发货",
        "净重 2.5kg",
        2500,
        ("全国非偏远地区",),
        "下单后 24 小时内发货",
    ),
    DemoSku(
        "YN-BLUEBERRY-6",
        "云南蓝莓 6盒装",
        "89.00",
        45,
        "L25",
        "云南澄江",
        "澄江蓝莓基地",
        "清甜脆爽",
        "即食",
        "125g×6 盒",
        750,
        ("华东", "华南", "西南"),
        "全程冷链，次日发出",
    ),
    DemoSku(
        "SX-PEAR-9",
        "山西玉露香梨 9枚",
        "45.90",
        0,
        "玉露香",
        "山西隰县",
        "隰县梨园",
        "细腻汁多",
        "即食",
        "9 枚礼盒",
        3000,
        ("华北", "华东"),
        "暂时售罄，等待补货",
    ),
)
