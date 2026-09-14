"""助手与业务数据说明契约；不允许模型自由生成元数据答案。"""

import re
import unicodedata
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

InformationTopic = Literal[
    "identity",
    "table_count",
    "tables",
    "date_range",
    "capabilities",
    "metrics",
    "dimensions",
    "data_source",
    "fields",
]


class InformationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    topics: list[InformationTopic] = Field(min_length=1, max_length=9)
    table: str | None = Field(default=None, max_length=100)
    metric: str | None = Field(default=None, max_length=80)


# 仅匹配完整的常见说明问题；不以关键词截获实际经营查询或复合问题。
FAQ_QUESTIONS: dict[InformationTopic, tuple[str, ...]] = {
    "identity": (
        "你是谁",
        "你叫什么",
        "你叫什么名字",
        "介绍一下你自己",
        "自我介绍",
        "你是什么助手",
        "你是做什么的",
        "你好",
    ),
    "table_count": (
        "有多少个数据表",
        "有多少张数据表",
        "有多少个表",
        "有几张表",
        "一共有多少张表",
        "业务数据表有多少张",
        "有多少张业务表",
        "数据表数量",
        "数据表有多少个",
    ),
    "tables": (
        "每个数据表是什么",
        "每张表是做什么的",
        "每个表的用途是什么",
        "有哪些数据表",
        "有哪些业务表",
        "有哪些表",
        "介绍一下各个数据表",
        "列出所有数据表",
        "数据表分别是什么",
        "业务数据表清单",
        "数据表介绍",
    ),
    "date_range": (
        "数据日期范围",
        "数据时间范围",
        "数据覆盖范围",
        "数据覆盖哪段时间",
        "数据从什么时候到什么时候",
        "数据更新到哪天",
        "数据截止到哪天",
        "数据截止日期",
        "最新数据是哪天的",
        "可以查询哪个时间段",
        "有哪些年份的数据",
    ),
    "capabilities": (
        "你能做什么",
        "你能帮我做什么",
        "你有哪些功能",
        "能问什么",
        "我可以问什么",
        "怎么使用",
        "使用帮助",
        "如何提问",
    ),
    "metrics": (
        "有哪些指标",
        "支持哪些指标",
        "可以查询哪些指标",
        "指标口径是什么",
        "指标怎么计算",
    ),
    "dimensions": ("支持哪些分析维度", "有哪些维度", "可以按什么维度分析"),
    "data_source": (
        "数据从哪里来",
        "数据来源是什么",
        "数据是真实的吗",
        "这些是真实数据吗",
        "数据是实时的吗",
        "多久更新一次",
    ),
    "fields": (),
}


def recognize_information(question: str) -> InformationRequest | None:
    normalized = unicodedata.normalize("NFKC", question).strip()
    normalized = re.sub(r"^(?:请问|请告诉我|请帮我看看|请)", "", normalized)
    normalized = re.sub(r"[\s?？。!！]+$", "", normalized)
    normalized = normalized.removesuffix("呢").removesuffix("吗")
    for topic, questions in FAQ_QUESTIONS.items():
        for candidate in questions:
            candidate = candidate.removesuffix("呢").removesuffix("吗")
            if normalized == candidate:
                return InformationRequest(topics=[topic])
    return None
