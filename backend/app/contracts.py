"""问数服务与持久化边界的内部契约，不包含 HTTP 对象。"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Literal, NotRequired, TypedDict

from pydantic import JsonValue

from .semantic import MasterDataPlan, Plan

QueryPlan = Plan | MasterDataPlan
RunStatus = Literal["success", "clarify", "unsupported", "error", "cancelled"]


class DatasetInfo(TypedDict):
    id: int
    version: str
    seed: int
    start_date: date
    cutoff_date: date
    counts: dict[str, int]
    created_at: datetime


class DisplayExecution(TypedDict):
    name: NotRequired[str]
    executable_sql: str
    business_sql: str


class SqlExecution(DisplayExecution):
    sql: str
    parameters: dict[str, str]


class AnalysisStep(TypedDict):
    key: str
    title: str
    status: str
    items: list[str]
    executions: NotRequired[list[DisplayExecution]]


class ResultRow(TypedDict):
    label: str
    dimensions: dict[str, str]
    value: float | None
    previous: float | None
    change: float | None
    difference: float | None


class RecordColumn(TypedDict):
    key: str
    title: str


class MetricDescription(TypedDict):
    name: str
    unit: str
    definition: str
    facts: NotRequired[list[str]]


class ComparisonRange(TypedDict):
    start: str
    end: str


class QueryResult(TypedDict, total=False):
    # 主数据、指标结果及旧历史结果具有不同字段集合；字段缺失不等同于零值。
    rows: list[ResultRow]
    records: list[dict[str, JsonValue]]
    record_columns: list[RecordColumn]
    total_count: int
    total: float | None
    previous_total: float | None
    difference: float | None
    change: float | None
    group_count: int
    truncated: bool
    empty: bool
    executions: list[SqlExecution]
    comparison_range: ComparisonRange | None
    status: RunStatus
    error_code: str | None
    plan: dict[str, JsonValue]
    metric: MetricDescription
    dataset_version: str
    cutoff_date: str
    model: str
    duration_ms: int
    completed_at: str
    usage: dict[str, int]
    analysis_process: list[AnalysisStep]
    suggestions: list[str]


class HistoryMessage(TypedDict):
    role: str
    content: str


class AssistantMessage(TypedDict):
    id: str
    role: Literal["assistant"]
    content: str
    result: QueryResult


class StatusEvent(TypedDict):
    type: Literal["status"]
    stage: str
    detail: str


class AnalysisEvent(TypedDict):
    type: Literal["analysis"]
    step: AnalysisStep


class ResultEvent(TypedDict):
    type: Literal["result"]
    message: AssistantMessage


StreamEvent = StatusEvent | AnalysisEvent | ResultEvent


@dataclass(frozen=True)
class AskContext:
    conversation_id: str
    user_id: int
    question: str
    model: str
    suggestions_enabled: bool
    previous_plan: dict[str, JsonValue]
    history: list[HistoryMessage]


@dataclass
class QueryRun:
    message_id: str
    context: AskContext
    status: RunStatus = "error"
    content: str = ""
    error_code: str | None = None
    plan: QueryPlan | None = None
    result: QueryResult = field(default_factory=dict)
    usage: dict[str, int] = field(default_factory=dict)
    dataset_version: str | None = None
    retrieval_audit: dict[str, JsonValue] | None = None
    duration_ms: int = 0

    def message(self) -> AssistantMessage:
        # 失败/取消不能携带先前生成的成功状态或半成品图表；审计仍保留执行信息。
        if self.status == "success":
            result: QueryResult = {**self.result, "status": self.status}
        elif self.status in {"clarify", "unsupported"}:
            result = {"status": self.status}
        else:
            result = {"status": self.status, "error_code": self.error_code}
        return {
            "id": self.message_id,
            "role": "assistant",
            "content": self.content,
            "result": result,
        }
