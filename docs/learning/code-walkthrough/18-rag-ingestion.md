# 18 RAG 加载、切分、嵌入与词法检索

本篇沿真实摄取顺序解释 loader、splitter、FakeEmbedding、BM25、查询改写、离线装配和 KnowledgeProvider Adapter。HybridRetriever 的融合流程见 [11 Hybrid Retrieval](11-hybrid-retrieval.md)。

## `rag/loader.py`

源码：[src/incident_copilot/rag/loader.py](../../../src/incident_copilot/rag/loader.py)

`MarkdownDocumentLoader.__init__` 立即 `resolve()` 根目录。`load()` 随后按以下顺序防御：根必须是目录；`rglob("*.md")` 后排序；每个 resolved path 必须仍在根内；每个文件解析为 `KnowledgeDocument`；document ID 不得重复；最终返回 tuple。

`_load_file()` 的逐语句流程：

1. 先用 stat 拒绝超过 1 MB 的文件，避免无界读取。
2. 按 UTF-8 读取并统一 CRLF/CR 换行。
3. 第一行必须是 `+++`。
4. `next(...)` 找结束分隔符；找不到时把 `StopIteration` 转成带路径的 `KnowledgeLoadError`。
5. `tomllib.loads` 只解析 frontmatter，正文不当 TOML。
6. 正文计算规范 SHA-256，与 metadata 合并。
7. 最后 Pydantic 校验 URI、标签、时间、内容和哈希；错误统一转换并保留原因链。

## `rag/splitter.py`

源码：[src/incident_copilot/rag/splitter.py](../../../src/incident_copilot/rag/splitter.py)

`tokenize()` 用共享正则提取英文标识符或单个中日韩字符并 `casefold()`。这不是模型 tokenizer，只用于确定性切分和 BM25。

构造器限制 `max_tokens` 在 20..2000，overlap 非负且小于窗口一半，保证滑窗 `step` 永远为正。

### `split` 的两阶段设计

第一阶段 `_sections()` 用标题栈把 Markdown 划成章节：普通行进入 body；遇到标题先 flush 旧正文；标题级别决定截断栈的位置；文件结束再次 flush。切分绝不跨显式标题。

第二阶段 `_split_section()`：先构造 `Section: ...` 前缀并扣除其 Token；短正文一次返回；长正文按 `available - overlap` 滑动。通过正则 match 的字符 offset 从原文截片，而不是把 token 用空格重新拼接，因此标点和格式仍保留。

`split()` 最后为每块生成 `document_id + ordinal + hash` 稳定 ID，并创建带 section/ordinal locator 的 Citation。相同输入重复摄取会得到相同 Chunk ID。

## `rag/embeddings.py`

源码：[src/incident_copilot/rag/embeddings.py](../../../src/incident_copilot/rag/embeddings.py)

`FakeEmbedding.embed()` 逐行执行：分词；建立固定维度零向量；每个 token 用 BLAKE2b 生成稳定 digest；前 8 字节选择 bucket；第 9 字节选择正负号；同 bucket 累加；最后除以 L2 norm 得单位向量。空文本和零向量明确报错。

它只验证向量检索的数据流和接口，不代表真实语义质量。`embed_many()` 简单按输入顺序调用 `embed`，不隐藏批处理或网络行为。

## `rag/bm25.py`

源码：[src/incident_copilot/rag/bm25.py](../../../src/incident_copilot/rag/bm25.py)

`rebuild()` 用 chunk ID 构造去重字典，逐块保存词频 Counter、文档长度，并按每个词是否出现更新 document frequency，最后计算平均长度。

`search()` 先限制 top_k，查询词稳定去重，随后对每个通过 metadata filter 的 Chunk：读取词频；对每个查询词计算平滑 IDF；用 k1/b 做文档长度归一化；只保留正分；最终按 `(-score, chunk_id)` 排序。同分时 ID 提供确定性结果。

BM25 的“文档”在这里实际是一条 KnowledgeChunk。删除 metadata filter 会让别的服务或未来文档进入结果。

## `rag/rewrite.py`

源码：[src/incident_copilot/rag/rewrite.py](../../../src/incident_copilot/rag/rewrite.py)

两个 `ClassVar` 词表分别处理中文短语和英文 token。`rewrite()` 规范化大小写/空白，用正则提词，内部 `append()` 保持顺序去重；先保留原词并扩展 token，再扫描中文短语扩展。它不调用 LLM，词表可审计，且绝不删除原查询词。

## `rag/bootstrap.py`

源码：[src/incident_copilot/rag/bootstrap.py](../../../src/incident_copilot/rag/bootstrap.py)

`repository_knowledge_root()` 从当前文件向上三级定位仓库，不依赖运行目录。`build_fixture_retriever()` 按顺序创建 64 维 FakeEmbedding、Splitter、BM25、内存向量库、Rewriter 和 HybridRetriever；接着加载文档并立即 `ingest`；返回 retriever 与实际计数结果。

## `rag/provider.py`

源码：[src/incident_copilot/rag/provider.py](../../../src/incident_copilot/rag/provider.py)

两种查询都先构造 `SearchQuery`：Runbook 固定 `DocumentType.RUNBOOK`；历史故障固定 INCIDENT，并用 before/lookback 组成有效时间过滤。同步检索通过 `asyncio.to_thread` 移出事件循环。

`_to_evidence()` 对每个 SearchHit：用内容哈希生成稳定 Evidence ID；来源固定 KNOWLEDGE；原 chunk 文本作为 content 和截断摘要；RAG score 作为 relevance；Runbook reliability 0.9、历史故障 0.85；保留 document/chunk/matched_by metadata；最关键的是直接复用 `chunk.citation`，模型不能改写出处。

## State 与工程类比

这些模块不直接写 State。只有 Tool Registry 收到 RagKnowledgeProvider 返回的 Evidence 后，collect Node 才把 `EvidenceRef` 追加进 State。整条链路类似搜索系统的 ETL + 双索引 + 查询 Adapter。

## 对照测试

- `tests/unit/rag/test_loader_splitter.py`
- `tests/unit/rag/test_embeddings_bm25.py`
- `tests/integration/test_rag_pipeline.py`

下一篇：[RAG Schema 与向量存储](19-rag-schemas-vector-store.md)。
