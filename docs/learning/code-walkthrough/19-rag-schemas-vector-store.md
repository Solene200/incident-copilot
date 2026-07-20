# 19 RAG Schema 与向量存储

本篇解释 RAG 的全部值对象、统一元数据过滤，以及内存/pgvector 两个 VectorStore Adapter。

## `rag/schemas.py`

源码：[src/incident_copilot/rag/schemas.py](../../../src/incident_copilot/rag/schemas.py)

### 文本规范化和哈希

`normalize_document_text()` 统一三种换行、去掉每行尾部空白、去掉全文首尾空白并拒绝空内容。`content_sha256()` 只对规范化结果计算哈希，所以 Windows/Linux 换行差异不会制造新文档版本。

`SEARCH_TOKEN_PATTERN` 同时识别英文技术标识和单个中文字符，是 Splitter、BM25 与 SearchQuery 的共享可搜索定义。

### 从 Document 到 RetrievalResult

| 模型 | 代码中的位置 | 关键不变量 |
| --- | --- | --- |
| `KnowledgeDocument` | Loader 输出 | URI 安全、标签规范、正文哈希匹配 |
| `KnowledgeChunk` | Splitter 输出 | 稳定 ID、正文哈希、Citation 哈希一致 |
| `EmbeddedChunk` | 向量入库值 | 向量有限且非全零，记录模型版本 |
| `ScoredChunk` | 单个后端候选 | score 非负 |
| `IngestResult` | 摄取统计 | 四个真实非负计数 |
| `MetadataFilter` | 两个检索后端共同输入 | 服务/环境/类型/有效时间白名单 |
| `SearchQuery` | Retriever 输入 | 查询有可搜索 token，top_k 有界 |
| `SearchHit` | 融合后命中 | score 归一化到 0..1，rank 有界 |
| `RetrievalResult` | 完整输出 | 同时保留原查询、改写查询、索引规模和时间 |

`KnowledgeDocument.validate_content_hash()` 重新计算正文哈希；`KnowledgeChunk.validate_hash_and_citation()` 再验证 Chunk 哈希与 Citation。即使 Loader/Splitter 有 bug，模型边界仍会拒绝不一致数据。

`EmbeddedChunk.validate_embedding()` 使用 `math.isfinite` 拒绝 NaN/Infinity，并拒绝全零向量，避免余弦相似度无定义。

### `MetadataFilter`

服务和环境 validator 负责规范化。模型 validator 要求 `effective_after < effective_before`。命名表示文档必须晚于 after 且早于 before。

`chunk_matches_filter()` 对每个约束采用“过滤器为空则不过滤”：服务/环境要求集合有交集；类型要求成员包含；时间边界使用严格 `<`/`>`，等于截止点的文档不算历史文档。BM25 与 VectorStore 都调用这个函数，避免两路候选语义不同。

## `rag/vector_store.py` 的端口

源码：[src/incident_copilot/rag/vector_store.py](../../../src/incident_copilot/rag/vector_store.py)

`VectorStore` Protocol 只声明 delete、upsert、原子 replace 和 search。HybridRetriever 依赖该端口，不依赖内存字典或 SQL。

## `InMemoryVectorStore`

### 写入采用复制后替换

`upsert()` 先把 records 固化为 tuple 并全部校验，再复制 `_records`，应用修改，最后一次性替换引用。若中途某向量非法，旧索引完全不变。

`replace_documents()` 同样先验证全部记录，再从副本排除目标 document ID、写入新 chunk、最后替换。这模拟数据库事务的 all-or-nothing 语义。

### 查询逐行理解

1. 校验 top_k 和查询向量。
2. 计算查询 L2 norm。
3. 遍历记录，只接受相同 embedding model/version。
4. 应用共享 metadata filter。
5. `zip(..., strict=True)` 计算点积，维度不同会立即报错。
6. 点积除以两端 norm 得 cosine。
7. 只保留正相似度，按负分数和 chunk ID 稳定排序。

## `PgVectorSession` 与 `PgVectorStore`

`PgVectorSession` 把 execute、transaction、fetch_all 缩成最小 SQL 端口，可由 psycopg 或 SQLAlchemy wrapper 实现。项目不因此把任一客户端变成默认依赖。

构造器验证维度和表名安全正则。表名无法使用 SQL 参数占位符，所以只允许安全标识符；所有数据值仍参数化。

### upsert 与 replace

`upsert()` 为每个 EmbeddedChunk 执行 `INSERT ... ON CONFLICT (chunk_id) DO UPDATE`。payload 保存完整经过验证的 JSON，独立列保存常用过滤字段和 vector。`replace_documents()` 用 session transaction 包住 delete + upsert，任一步失败都应回滚。

### search 动态条件

代码先固定 model/version 条件，再按非空 metadata filter 追加 SQL 和参数。`WHERE` 只由代码生成的白名单片段组成，用户值全部进入 parameter tuple。查询使用 `<=>` cosine distance，`1 - distance` 转相似度，并以同一 query vector 排序。

返回行逐项经过 `EmbeddedChunk.model_validate`，随后再次检查模型身份和 score 的类型/有限性。注意 `bool` 是 `int` 子类，所以代码显式排除 bool。只有正 score 转成 ScoredChunk。

`_vector_literal()` 用 17 位有效数字序列化 float，既可往返双精度，又不拼接用户文本。

## 初始化文件与 State

[`rag/__init__.py`](../../../src/incident_copilot/rag/__init__.py) 重新导出端口、Schema、Loader、Splitter、Retriever 和 Adapter，构成 RAG 公共门面。它不自动加载知识库或连接 PostgreSQL。

RAG Schema 和 VectorStore 都不直接接触 Graph State；RagKnowledgeProvider 是进入 Tool/Evidence 契约的唯一桥梁。

## 修改风险与测试

- 去掉 embedding version 过滤会混合不同向量空间。
- delete 后不加事务就 upsert，失败时会丢失旧索引。
- 把表名直接接受用户输入会产生 SQL 注入风险。
- 两个后端采用不同 metadata 边界会让融合结果不可解释。

对照测试：`tests/unit/rag/test_vector_store.py`、`tests/unit/rag/test_retrieval.py`、`tests/integration/test_rag_pipeline.py`。

下一篇：[Tool 契约与内置工具](20-tool-contracts-builtin.md)。
