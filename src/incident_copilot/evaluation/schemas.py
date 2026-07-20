"""确定性离线评估使用的已校验输入输出契约。"""

from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, JsonValue, field_validator, model_validator

from incident_copilot.domain.common import (
    AwareDatetime,
    DomainModel,
    normalize_services,
    unique_evidence_ids,
    unique_non_empty,
)
from incident_copilot.domain.report import IncidentReport


class SampleStatus(StrEnum):
    """表示样例生成了报告还是保留了 Runner 失败。"""

    COMPLETED = "completed"  # 样例成功运行 Graph 并生成报告。
    FAILED = "failed"  # 样例运行失败但错误仍保留在原始结果中。


class ExpectedToolCall(DomainModel):
    """预期工具及其与真实标签相关的参数字段。"""

    # 标签期望调查选择的工具名称。
    tool_name: str = Field(pattern=r"^[a-z][a-z0-9_]{1,63}$")
    # 只包含需要评分的关键参数字段, 未标注参数不扣分。
    arguments: dict[str, JsonValue] = Field(default_factory=dict)


class EvaluationGroundTruth(DomainModel):
    """不向 Graph 暴露、仅在推理完成后使用的标签。"""

    # 该样例真实受影响的服务。
    affected_services: tuple[str, ...] = Field(min_length=1, max_length=20)
    # 该样例预先标注的故障类型名称。
    failure_type: str = Field(pattern=r"^[a-z][a-z0-9_]{1,63}$")
    # 准确根因文本应该覆盖的关键因果词组。
    root_cause_terms: tuple[str, ...] = Field(min_length=1, max_length=20)
    # 标签认为与根因直接相关的 Evidence ID。
    relevant_evidence_ids: tuple[str, ...] = Field(default_factory=tuple, max_length=100)
    # 标签认为 RAG 应召回的 KnowledgeDocument ID。
    relevant_document_ids: tuple[str, ...] = Field(default_factory=tuple, max_length=100)
    # 标签期望调查选择的工具和关键参数。
    expected_tools: tuple[ExpectedToolCall, ...] = Field(default_factory=tuple, max_length=20)

    @field_validator("affected_services")
    @classmethod
    def validate_services(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return normalize_services(values)

    @field_validator("root_cause_terms", "relevant_document_ids")
    @classmethod
    def validate_text_collections(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return unique_non_empty(values, field_name="evaluation labels")

    @field_validator("relevant_evidence_ids")
    @classmethod
    def validate_evidence_ids(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return unique_evidence_ids(values, field_name="relevant evidence ids")

    @model_validator(mode="after")
    def validate_unique_tools(self) -> Self:
        names = [item.tool_name for item in self.expected_tools]
        if len(names) != len(set(names)):
            raise ValueError("expected tool names must be unique per sample")
        return self


class EvaluationSample(DomainModel):
    """一次可复现的事故调用及其仅供评估器使用的标签。"""

    # 离线评估样例的唯一标识, 统一使用 eval_ 前缀。
    sample_id: str = Field(pattern=r"^eval_[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
    # 相对于仓库根目录的事故 Fixture JSON 路径。
    fixture_path: str = Field(min_length=1, max_length=512)
    # 单独评估 RAG 召回时使用的查询文本。
    retrieval_query: str = Field(min_length=2, max_length=512)
    # 计算 Recall@K 和 MRR 时查看的最大排名 K。
    retrieval_top_k: int = Field(default=5, ge=1, le=50)
    # Graph 完成后才交给评估器的真实标签。
    ground_truth: EvaluationGroundTruth
    # 用于对样例按场景分类的标签。
    tags: tuple[str, ...] = Field(default_factory=tuple, max_length=20)

    @field_validator("fixture_path")
    @classmethod
    def validate_relative_fixture_path(cls, value: str) -> str:
        path = Path(value)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("fixture_path must be a repository-relative path")
        return path.as_posix()

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return unique_non_empty(values, field_name="evaluation tags")


class EvaluationDataset(DomainModel):
    """供离线运行比较使用的不可变版本化集合。"""

    # 评估数据集 JSON 外层结构的版本。
    schema_version: Literal["1.0"] = "1.0"
    # 数据集的稳定唯一标识。
    dataset_id: str = Field(pattern=r"^dataset_[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
    # 数据集内容版本, 用于比较不同运行结果。
    version: str = Field(min_length=1, max_length=64)
    # 数据集覆盖范围和目的说明。
    description: str = Field(min_length=1, max_length=1_000)
    # 本次数据集包含的全部离线评估样例。
    samples: tuple[EvaluationSample, ...] = Field(min_length=1, max_length=1_000)

    @model_validator(mode="after")
    def validate_unique_samples(self) -> Self:
        ids = [sample.sample_id for sample in self.samples]
        if len(ids) != len(set(ids)):
            raise ValueError("evaluation sample ids must be unique")
        return self


class SetMetrics(DomainModel):
    """具有明确计数和空集合语义的可审计集合比较。"""

    # 标签集合去重后的元素数量。
    expected_count: int = Field(ge=0)
    # 系统预测集合去重后的元素数量。
    actual_count: int = Field(ge=0)
    # 同时出现在标签和预测集合中的正确元素数量。
    true_positive_count: int = Field(ge=0)
    # 预测结果中有多少比例真正正确。
    precision: float = Field(ge=0.0, le=1.0)
    # 标签要求的正确结果中有多少比例被找回。
    recall: float = Field(ge=0.0, le=1.0)
    # precision 与 recall 的调和平均。
    f1: float = Field(ge=0.0, le=1.0)
    # 预测集合是否与标签集合完全相同。
    exact_match: bool


class ToolArgumentMetrics(DomainModel):
    """比较参数子集,不惩罚标签未指定的运行时字段。"""

    # 标签明确要求比较的工具参数字段总数。
    expected_field_count: int = Field(ge=0)
    # 实际调用中值完全匹配的标签参数字段数。
    matched_field_count: int = Field(ge=0)
    # matched_field_count 除以 expected_field_count 的比例。
    score: float = Field(ge=0.0, le=1.0)


class RetrievalMetrics(DomainModel):
    """带排名的检索标签和可手工核对的 Recall@K/MRR 输出。"""

    # 本次检索指标只检查排名前 K 个结果。
    top_k: int = Field(ge=1, le=50)
    # 标签期望检索到的文档 ID。
    expected_document_ids: tuple[str, ...]
    # 系统按相关性返回并去重后的文档 ID 排名。
    ranked_document_ids: tuple[str, ...]
    # 前 K 个结果覆盖了多少比例的相关文档。
    recall_at_k: float = Field(ge=0.0, le=1.0)
    # 第一个相关文档排名的倒数, 没命中时为 0。
    reciprocal_rank: float = Field(ge=0.0, le=1.0)


class CitationMetrics(DomainModel):
    """报告中每个 EvidenceRef 的精确引用完整性。"""

    # 报告中实际检查了多少条 EvidenceRef。
    checked_evidence_count: int = Field(ge=0)
    # Citation ID、URI、locator 和哈希都正确的数量。
    correct_citation_count: int = Field(ge=0)
    # 正确引用比例, 没有 EvidenceRef 时为 None。
    score: float | None = Field(default=None, ge=0.0, le=1.0)


class ActualToolCall(DomainModel):
    """根据已执行计划重建的原始工具完成记录。"""

    # 从 Graph StepResult 重建的实际工具名称。
    tool_name: str
    # 实际提交给工具的 JSON 参数。
    arguments: dict[str, JsonValue]
    # 实际工具步骤终止状态。
    status: str
    # 实际工具步骤收集到的 Evidence ID。
    evidence_ids: tuple[str, ...]


class SampleUsage(DomainModel):
    """实际测量的 Graph 计数、明确的 Token 来源和不可用成本。"""

    # 单样例实际执行的研究轮数。
    research_rounds: int = Field(ge=0)
    # 单样例实际尝试的工具调用数。
    tool_calls: int = Field(ge=0)
    # 单样例实际调用模型 Provider 的次数。
    model_calls: int = Field(ge=0)
    # 单样例从开始到结束的实测毫秒数。
    latency_ms: float = Field(ge=0.0)
    # 单样例累计输入 Token 数。
    input_tokens: int = Field(ge=0)
    # 单样例累计输出 Token 数。
    output_tokens: int = Field(ge=0)
    # 输入和输出 Token 之和。
    total_tokens: int = Field(ge=0)
    # Token 是否来自 Fake Model 的估算值。
    token_usage_estimated: bool
    # 未接真实模型定价时成本没有可信数值, 固定为 None。
    estimated_cost_usd: None = None
    # 明确说明成本不可用是因为没有模型定价。
    cost_status: Literal["unavailable_no_pricing"] = "unavailable_no_pricing"


class EvaluationSampleResult(DomainModel):
    """即使样例失败也会保留的原始可追踪结果。"""

    # 被评估样例的唯一标识, 用来关联输入数据和原始结果。
    sample_id: str
    # 样例最终是正常完成还是执行失败。
    status: SampleStatus
    # 执行失败时保存的错误摘要; 成功时必须为空。
    error: str | None = Field(default=None, max_length=2_000)
    # 调查报告实际定位到的服务名称集合。
    predicted_services: tuple[str, ...] = ()
    # 调查报告实际判断的故障类型。
    predicted_failure_type: str | None = None
    # 调查报告实际生成的根因描述。
    root_cause: str | None = None
    # 服务定位结果与标准答案比较后的集合指标。
    service_localization: SetMetrics | None = None
    # 预测故障类型是否与标准答案一致。
    failure_type_correct: bool | None = None
    # RAG 检索的 Recall@K 和 MRR 指标。
    retrieval: RetrievalMetrics | None = None
    # 实际工具集合与期望工具集合的比较指标。
    tool_selection: SetMetrics | None = None
    # 实际工具参数与期望参数的比较指标。
    tool_arguments: ToolArgumentMetrics | None = None
    # 报告所用证据与标准相关证据的比较指标。
    evidence_relevance: SetMetrics | None = None
    # 报告引用是否存在、是否匹配证据的统计指标。
    citations: CitationMetrics | None = None
    # 根因描述覆盖标准答案关键词的比例。
    root_cause_term_recall: float | None = Field(default=None, ge=0.0, le=1.0)
    # 根因关键词召回率是否达到项目设定的正确阈值。
    root_cause_accurate: bool | None = None
    # 本次样例执行期间实际发生的工具调用记录。
    actual_tool_calls: tuple[ActualToolCall, ...] = ()
    # 本次执行的轮数、调用数、耗时和 Token 用量。
    usage: SampleUsage | None = None
    # 调查成功时保存的完整故障报告。
    report: IncidentReport | None = None

    @model_validator(mode="after")
    def validate_status(self) -> Self:
        if self.status is SampleStatus.COMPLETED and (
            self.report is None or self.error is not None
        ):
            raise ValueError("completed evaluation sample requires a report and no error")
        if self.status is SampleStatus.FAILED and not self.error:
            raise ValueError("failed evaluation sample requires an error")
        return self


class AggregateMetrics(DomainModel):
    """完成样例的均值,可选指标会排除分母未定义的情况。"""

    # 正确定位故障服务的样例比例。
    service_localization_accuracy: float | None = Field(default=None, ge=0.0, le=1.0)
    # 正确判断故障类型的样例比例。
    failure_type_accuracy: float | None = Field(default=None, ge=0.0, le=1.0)
    # 各样例检索 Recall@K 的平均值。
    retrieval_recall_at_k: float | None = Field(default=None, ge=0.0, le=1.0)
    # 各样例检索倒数排名 MRR 的平均值。
    retrieval_mrr: float | None = Field(default=None, ge=0.0, le=1.0)
    # 各样例工具选择 F1 的平均值。
    tool_selection_f1: float | None = Field(default=None, ge=0.0, le=1.0)
    # 各样例工具参数准确率的平均值。
    tool_argument_accuracy: float | None = Field(default=None, ge=0.0, le=1.0)
    # 各样例证据相关性 F1 的平均值。
    evidence_relevance_f1: float | None = Field(default=None, ge=0.0, le=1.0)
    # 各样例引用正确率的平均值。
    citation_correctness: float | None = Field(default=None, ge=0.0, le=1.0)
    # 根因判断达到正确阈值的样例比例。
    root_cause_accuracy: float | None = Field(default=None, ge=0.0, le=1.0)
    # 已完成样例平均使用的调查轮数。
    mean_research_rounds: float | None = Field(default=None, ge=0.0)
    # 已完成样例平均尝试的工具调用次数。
    mean_tool_calls: float | None = Field(default=None, ge=0.0)
    # 已完成样例的平均执行耗时, 单位为毫秒。
    mean_latency_ms: float | None = Field(default=None, ge=0.0)
    # 已完成样例耗时的第 95 百分位数, 单位为毫秒。
    p95_latency_ms: float | None = Field(default=None, ge=0.0)
    # 所有已完成样例累计消耗的 Token 数。
    total_tokens: int = Field(ge=0)
    # 每个已完成样例平均消耗的 Token 数。
    mean_tokens: float | None = Field(default=None, ge=0.0)
    # 聚合的 Token 用量是否来自 Fake Model 估算。
    token_usage_estimated: bool | None = None
    # 未接真实模型定价时没有可信成本数值, 固定为空。
    estimated_cost_usd: None = None
    # 明确标记成本不可用的原因是缺少模型定价。
    cost_status: Literal["unavailable_no_pricing"] = "unavailable_no_pricing"


class EvaluationSummary(DomainModel):
    """与一个数据集版本和原始结果产物关联的聚合报告。"""

    # 汇总报告的数据结构版本, 便于将来兼容旧产物。
    schema_version: Literal["1.0"] = "1.0"
    # 本次评估运行的唯一标识。
    run_id: str = Field(pattern=r"^evalrun_[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
    # 本次使用的评估数据集标识。
    dataset_id: str
    # 本次使用的数据集版本。
    dataset_version: str
    # 整次评估开始执行的时间。
    started_at: AwareDatetime
    # 整次评估完成的时间。
    completed_at: AwareDatetime
    # 数据集中参与本次运行的样例总数。
    sample_count: int = Field(ge=0)
    # 正常完成并进入指标聚合的样例数。
    completed_sample_count: int = Field(ge=0)
    # 执行失败但仍保留原始错误结果的样例数。
    failed_sample_count: int = Field(ge=0)
    # 由全部已完成样例计算出的聚合指标。
    metrics: AggregateMetrics
    # 原始逐样例结果文件相对于输出目录的路径。
    raw_results_file: str
    # 阅读评估数字时必须同时了解的限制说明。
    limitations: tuple[str, ...]
    # 汇总报告文件实际生成的时间。
    generated_at: AwareDatetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def validate_counts(self) -> Self:
        if self.completed_sample_count + self.failed_sample_count != self.sample_count:
            raise ValueError("evaluation sample counts must balance")
        if self.completed_at < self.started_at:
            raise ValueError("evaluation completion must not precede start")
        return self
