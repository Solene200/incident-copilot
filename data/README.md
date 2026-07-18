# Fixture data layout

Fixture 文件使用版本化 `IncidentFixture` envelope，并由 Phase 2 FixtureProvider 在加载时完整校验。

- `incidents/example.json`：Phase 1 的最小 Schema 样例。
- `incidents/payment-service-pool-exhaustion.json`：Phase 2 基准事件，包含日志、指标、Trace、变更、拓扑、Runbook 和历史事故证据。
- 每条 Evidence 都包含来源类型/名称、时间点或时间窗口、服务与可解析 citation。
- `ground_truth` 只供测试与 Evaluation 使用，FixtureProvider 不通过任何工具返回该字段。
- Fixture 不得包含真实客户、凭据、Token、支付信息或个人信息。

基准事件的预期根因是发布将数据库连接池上限从 50 降至 5。数据同时包含健康的外部网关指标、健康检查 Trace 和合成拒绝日志，分别用于反证外部网关首因和模拟调查噪声；这些是可审阅的设计事实，不是模型评估结果。
