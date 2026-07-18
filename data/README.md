# Fixture data layout

Phase 1 只定义版本化 Fixture Schema 和一个脱敏结构样例，不包含 Provider 查询实现。

- `incidents/`：每个 JSON 文件表示一个 `IncidentFixture`。
- 未来 Phase 2 会按 logs、metrics、traces、changes、topology 等来源扩展原始数据目录。
- `ground_truth` 只供测试与 Evaluation 使用，未来不得进入 Agent 可见上下文。
- Fixture 不得包含真实客户、凭据、Token、支付信息或个人信息。

