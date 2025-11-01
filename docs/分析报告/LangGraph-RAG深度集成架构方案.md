# LangGraph + RAG 深度集成架构方案

**分析时间**: 2025-10-27
**分析方法**: LangGraph文档研究 + 现有代码审查 + 架构设计
**核心问题**: 如何将先进RAG技术（Hybrid Search, ColBERT, Graph RAG, Self-RAG）正确集成到LangGraph工作流中？

---

## 📋 执行摘要

### 核心发现

**当前架构（简单依赖注入）**:
```python
# src/emergency_agents/graph/app.py
def risk_prediction_node(state):
    return risk_predictor_agent(state, kg_service, rag_pipeline, llm_client, cfg.llm_model)
    #                                              ^^^^^^^^^^^^
    #                                         RAG作为参数注入
```

**问题分析**:
1. ❌ RAG与LangGraph状态机隔离，无法利用checkpointing/interrupt特性
2. ❌ 无法实现"检索→评估→重检索"的Self-RAG循环
3. ❌ Graph RAG的KG+RAG融合逻辑隐藏在agent内部，不可观测
4. ✅ 简单直接，易于理解（但可扩展性差）

### 推荐方案（分层架构）

**三层集成策略**（根据复杂度递增）:

| 层级 | 技术 | 集成方式 | 优先级 | 实施时间 |
|------|------|---------|--------|---------|
| **L1: 库升级** | Hybrid Search + ColBERT | 升级`RagPipeline`内部实现 | ⭐⭐⭐⭐⭐ | 3天 |
| **L2: 节点化** | Self-RAG | 新增`self_rag_retrieve`条件节点 | ⭐⭐⭐⭐ | 5-7天 |
| **L3: 子图** | Graph RAG | 独立`GraphRAGSubgraph`子图 | ⭐⭐⭐ | 8-10天 |

**核心原则**:
1. **渐进式改造**: 不破坏现有工作流
2. **可观测性优先**: 关键决策点暴露为LangGraph节点
3. **类型安全**: 保持Python类型注解
4. **HITL友好**: 支持人工审批中断

---

## 🎯 L1层：库升级（Hybrid Search + ColBERT）

### 为什么不需要改LangGraph?

**理由**: Hybrid Search和ColBERT是**纯检索优化**，不涉及工作流逻辑变化。

### 实施方案

#### 升级前（现状）
```python
# src/emergency_agents/rag/pipe.py
class RagPipeline:
    def query(self, question: str, domain: str, top_k: int = 3) -> List[RagChunk]:
        # ❌ 只有密集向量检索
        vector_store = self._vector_store(f"rag_{domain}")
        index = VectorStoreIndex.from_vector_store(vector_store)
        engine = index.as_query_engine(similarity_top_k=top_k)
        response = engine.query(question)
        return self._parse_response(response)
```

#### 升级后（Hybrid + ColBERT）
```python
from llama_index.core.retrievers import QueryFusionRetriever
from llama_index.postprocessor.colbert_rerank import ColbertRerank

class EnhancedRagPipeline(RagPipeline):
    """增强型RAG管道：混合检索 + ColBERT重排序"""

    def __init__(self, *args, enable_hybrid: bool = True, enable_rerank: bool = True, **kwargs):
        super().__init__(*args, **kwargs)
        self.enable_hybrid = enable_hybrid
        self.enable_rerank = enable_rerank

        # ColBERT重排序器（仅在需要时初始化）
        if enable_rerank:
            self.reranker = ColbertRerank(
                model="colbert-ir/colbertv2.0",
                top_n=5,
                device="cuda"
            )

    def query(
        self,
        question: str,
        domain: str,
        top_k: int = 3,
        hybrid_alpha: float = 0.5  # 0=纯稀疏，1=纯密集，0.5=均衡
    ) -> List[RagChunk]:
        collection = f"rag_{domain}"
        vector_store = self._vector_store(collection)

        if self.enable_hybrid:
            # ✅ 混合检索（密集+稀疏）
            from llama_index.retrievers.bm25 import BM25Retriever
            from llama_index.core.retrievers import VectorIndexRetriever

            # 密集检索器
            dense_retriever = VectorIndexRetriever(
                index=VectorStoreIndex.from_vector_store(vector_store),
                similarity_top_k=top_k * 2  # 粗排多取一些
            )

            # 稀疏检索器（BM25）
            sparse_retriever = BM25Retriever.from_defaults(
                docstore=vector_store.docstore,
                similarity_top_k=top_k * 2
            )

            # 融合检索器
            retriever = QueryFusionRetriever(
                retrievers=[dense_retriever, sparse_retriever],
                similarity_top_k=top_k * 2,
                num_queries=1,  # 不做查询扩展
                mode="reciprocal_rerank",  # 倒数排序融合
                use_async=False
            )
        else:
            # 传统单一向量检索
            index = VectorStoreIndex.from_vector_store(vector_store)
            retriever = index.as_retriever(similarity_top_k=top_k * 2)

        # 粗排检索
        nodes = retriever.retrieve(question)

        if self.enable_rerank and len(nodes) > top_k:
            # ✅ ColBERT重排序（精排）
            nodes = self.reranker.postprocess_nodes(nodes, query_str=question)

        # 转换为RagChunk
        return [
            RagChunk(
                text=node.get_content(),
                score=node.get_score(),
                metadata=node.metadata
            )
            for node in nodes[:top_k]
        ]
```

### LangGraph集成（无需修改）

```python
# src/emergency_agents/graph/app.py
from emergency_agents.rag.enhanced_pipe import EnhancedRagPipeline

def build_app(...):
    # ✅ 直接替换，API兼容
    rag_pipeline = EnhancedRagPipeline(
        qdrant_url=cfg.qdrant_url,
        enable_hybrid=True,      # 启用混合检索
        enable_rerank=True,      # 启用ColBERT
        embedding_model=cfg.embedding_model,
        ...
    )

    # 其他代码完全不变
    def risk_prediction_node(state):
        return risk_predictor_agent(state, kg_service, rag_pipeline, llm_client, cfg.llm_model)

    graph.add_node("risk_prediction", risk_prediction_node)
```

### 优势
- ✅ **零破坏性**: 现有节点无需修改
- ✅ **快速见效**: 3天内检索精度提升20-30%
- ✅ **可配置**: 通过参数控制是否启用
- ✅ **向后兼容**: `EnhancedRagPipeline`继承自`RagPipeline`

---

## 🎯 L2层：节点化（Self-RAG）

### 为什么需要改LangGraph?

**理由**: Self-RAG的核心是"检索→评估→决策"循环，这是**工作流逻辑**，必须用LangGraph条件边表达。

### LangGraph标准模式

从LangGraph文档中学到的RAG最佳实践：

```python
# 来自 langgraph/references/agents.md - Local RAG agent with LLaMA3
def router_node(state):
    """路由节点：决定使用vectorstore还是web search"""
    router_instructions = """判断用户问题应该查询向量库还是网络搜索。
    返回JSON: {"datasource": "vectorstore" or "websearch"}"""

    decision = llm_json_mode.invoke([
        SystemMessage(content=router_instructions),
        HumanMessage(content=state["question"])
    ])
    return {"datasource": decision["datasource"]}

def route_question(state):
    """条件边：根据router_node的决策路由"""
    if state["datasource"] == "vectorstore":
        return "retrieve_from_rag"
    else:
        return "retrieve_from_web"

# 构建图
graph.add_node("router", router_node)
graph.add_node("retrieve_from_rag", rag_retrieve_node)
graph.add_node("retrieve_from_web", web_search_node)
graph.add_conditional_edges("router", route_question, {
    "retrieve_from_rag": "retrieve_from_rag",
    "retrieve_from_web": "retrieve_from_web"
})
```

### Self-RAG LangGraph实现

#### 状态扩展

```python
# src/emergency_agents/graph/app.py
class RescueState(TypedDict, total=False):
    # ... 现有字段 ...

    # Self-RAG专用字段
    self_rag_decision: Literal["retrieve", "generate", "skip"]
    self_rag_quality: Literal["good", "bad", "uncertain"]
    self_rag_attempt: int
    retrieved_contexts: list[dict]  # 存储检索到的上下文
```

#### 新增节点

```python
def self_rag_router_node(state: RescueState) -> dict:
    """Self-RAG决策节点：判断是否需要检索"""

    question = state.get("prompt", "")
    situation = state.get("situation", {})

    router_prompt = f"""作为应急救援专家，判断是否需要检索历史案例：

当前态势：{json.dumps(situation, ensure_ascii=False)}
问题：{question}

如果涉及具体救援经验、装备配置、方案生成，返回 {{"decision": "retrieve"}}
如果是简单的规则推理、数值计算，返回 {{"decision": "skip"}}

只返回JSON。"""

    response = llm_client.chat.completions.create(
        model=cfg.llm_model,
        messages=[{"role": "user", "content": router_prompt}],
        response_format={"type": "json_object"},
        temperature=0
    )

    decision = json.loads(response.choices[0].message.content)

    return {
        "self_rag_decision": decision.get("decision", "skip"),
        "self_rag_attempt": state.get("self_rag_attempt", 0) + 1
    }

def self_rag_retrieve_node(state: RescueState) -> dict:
    """Self-RAG检索节点：使用增强型RAG检索"""

    question = state.get("prompt", "")

    # 使用L1层的EnhancedRagPipeline
    contexts = rag_pipeline.query(
        question=question,
        domain="案例",
        top_k=5,
        hybrid_alpha=0.5
    )

    return {
        "retrieved_contexts": [
            {"text": c.text, "score": c.score, "metadata": c.metadata}
            for c in contexts
        ],
        "rag_case_refs_count": len(contexts)
    }

def self_rag_evaluator_node(state: RescueState) -> dict:
    """Self-RAG评估节点：评估检索质量"""

    contexts = state.get("retrieved_contexts", [])
    question = state.get("prompt", "")

    if not contexts:
        return {"self_rag_quality": "bad", "self_rag_decision": "generate"}

    eval_prompt = f"""评估检索到的案例是否能回答问题：

问题：{question}

案例片段：
{chr(10).join([f"{i+1}. {c['text'][:200]}" for i, c in enumerate(contexts[:3])])}

如果案例相关且包含可用信息，返回 {{"quality": "good"}}
如果案例不相关或信息不足，返回 {{"quality": "bad"}}

只返回JSON。"""

    response = llm_client.chat.completions.create(
        model=cfg.llm_model,
        messages=[{"role": "user", "content": eval_prompt}],
        response_format={"type": "json_object"},
        temperature=0
    )

    evaluation = json.loads(response.choices[0].message.content)
    quality = evaluation.get("quality", "uncertain")

    # 如果质量差且尝试次数<2，重新检索
    if quality == "bad" and state.get("self_rag_attempt", 0) < 2:
        return {
            "self_rag_quality": quality,
            "self_rag_decision": "retrieve"  # 触发重检索
        }

    return {
        "self_rag_quality": quality,
        "self_rag_decision": "generate"
    }
```

#### 条件边

```python
def route_self_rag(state: RescueState) -> str:
    """Self-RAG路由函数"""
    decision = state.get("self_rag_decision", "skip")

    if decision == "retrieve":
        return "self_rag_retrieve"
    elif decision == "generate":
        return "risk_prediction"  # 继续原有流程
    else:
        return "risk_prediction"  # skip也继续

# 构建图（修改部分）
graph.add_node("self_rag_router", self_rag_router_node)
graph.add_node("self_rag_retrieve", self_rag_retrieve_node)
graph.add_node("self_rag_evaluator", self_rag_evaluator_node)

# 原来: situation → risk_prediction
# 现在: situation → self_rag_router → (可选)retrieve+eval → risk_prediction
graph.add_edge("situation", "self_rag_router")
graph.add_conditional_edges("self_rag_router", route_self_rag, {
    "self_rag_retrieve": "self_rag_retrieve",
    "risk_prediction": "risk_prediction"
})
graph.add_edge("self_rag_retrieve", "self_rag_evaluator")
graph.add_conditional_edges("self_rag_evaluator", route_self_rag, {
    "retrieve": "self_rag_retrieve",  # 重检索循环
    "generate": "risk_prediction"
})
```

### 优势
- ✅ **可观测**: 每次Self-RAG决策都记录在checkpoint
- ✅ **可调试**: LangSmith追踪每个节点的输入输出
- ✅ **可中断**: 可在评估节点后人工审批
- ✅ **防死循环**: `self_rag_attempt`限制最大重试次数

### 注意事项
- ⚠️ 增加了2-3次LLM调用（router + evaluator）
- ⚠️ 延迟增加500-1000ms
- ⚠️ 只在"方案生成"等复杂场景启用

---

## 🎯 L3层：子图（Graph RAG）

### 为什么需要子图?

**理由**: Graph RAG是**复杂的多步骤工作流**，涉及：
1. RAG检索案例
2. LLM从案例中提取实体
3. Neo4j查询实体相关节点
4. 图推理（路径查询、社区检测）
5. 融合KG+RAG结果

这是一个**完整的子任务**，应封装为独立子图。

### LangGraph子图模式

从文档学到的子图最佳实践：

```python
# 来自 langgraph/references/agents.md - Subgraphs
from langgraph.graph import StateGraph, START

# 子图状态（可以与父图不同）
class GraphRAGState(TypedDict):
    query: str
    rag_contexts: list[dict]
    kg_entities: list[dict]
    kg_paths: list[dict]
    fused_result: dict

# 定义子图
def build_graph_rag_subgraph():
    subgraph = StateGraph(GraphRAGState)

    subgraph.add_node("rag_retrieve", rag_retrieve_node)
    subgraph.add_node("extract_entities", entity_extraction_node)
    subgraph.add_node("kg_query", kg_query_node)
    subgraph.add_node("graph_reasoning", graph_reasoning_node)
    subgraph.add_node("fusion", fusion_node)

    subgraph.add_edge(START, "rag_retrieve")
    subgraph.add_edge("rag_retrieve", "extract_entities")
    subgraph.add_edge("extract_entities", "kg_query")
    subgraph.add_edge("kg_query", "graph_reasoning")
    subgraph.add_edge("graph_reasoning", "fusion")

    return subgraph.compile()

# 父图集成（状态转换函数）
def graph_rag_adapter_node(state: RescueState) -> dict:
    """适配器节点：转换父图状态→子图状态→父图状态"""

    # 1. 父→子状态转换
    subgraph_input = GraphRAGState(
        query=state.get("prompt", ""),
        rag_contexts=[],
        kg_entities=[],
        kg_paths=[],
        fused_result={}
    )

    # 2. 调用子图
    graph_rag_subgraph = build_graph_rag_subgraph()
    result = graph_rag_subgraph.invoke(subgraph_input)

    # 3. 子→父状态转换
    return {
        "retrieved_contexts": result["rag_contexts"],
        "kg_hits_count": len(result["kg_entities"]),
        "rag_case_refs_count": len(result["rag_contexts"]),
        "graph_rag_result": result["fused_result"]
    }

# 父图中使用
graph.add_node("graph_rag", graph_rag_adapter_node)
```

### Graph RAG子图详细实现

#### 子图节点定义

```python
# src/emergency_agents/rag/graph_rag.py

from typing import TypedDict, List, Dict, Any
from langgraph.graph import StateGraph, START, END

class GraphRAGState(TypedDict, total=False):
    query: str
    disaster_type: str
    affected_area: str

    # 阶段1: RAG检索
    rag_contexts: List[Dict[str, Any]]

    # 阶段2: 实体提取
    extracted_entities: List[Dict[str, str]]  # {type, name, alias}

    # 阶段3: KG查询
    kg_nodes: List[Dict[str, Any]]
    kg_relationships: List[Dict[str, Any]]

    # 阶段4: 图推理
    reasoning_paths: List[List[str]]  # [[node1, rel, node2, ...]]
    subgraph: Dict[str, Any]  # 局部子图结构

    # 阶段5: 融合
    fused_result: Dict[str, Any]

def rag_retrieve_node_graphrag(state: GraphRAGState) -> dict:
    """阶段1: 使用增强型RAG检索历史案例"""
    from emergency_agents.rag.enhanced_pipe import EnhancedRagPipeline

    rag_pipeline = EnhancedRagPipeline(...)  # 从配置初始化

    contexts = rag_pipeline.query(
        question=state["query"],
        domain="案例",
        top_k=5,
        hybrid_alpha=0.5
    )

    return {
        "rag_contexts": [
            {
                "text": c.text,
                "score": c.score,
                "metadata": c.metadata
            }
            for c in contexts
        ]
    }

def entity_extraction_node(state: GraphRAGState) -> dict:
    """阶段2: 从RAG案例中提取实体"""
    from emergency_agents.llm.client import get_openai_client

    contexts_text = "\n\n".join([c["text"][:500] for c in state["rag_contexts"]])

    prompt = f"""从以下应急救援案例中提取关键实体：

案例：
{contexts_text}

提取规则：
1. 灾害类型（地震、洪水、滑坡等）
2. 地点（省市县、地标）
3. 装备（生命探测仪、挖掘机等）
4. 单位（消防、武警、医疗队等）

返回JSON格式：
{{
  "entities": [
    {{"type": "灾害", "name": "地震", "alias": ["earthquake"]}},
    {{"type": "装备", "name": "生命探测仪", "alias": []}}
  ]
}}

只返回JSON。"""

    llm = get_openai_client(...)
    response = llm.chat.completions.create(
        model="glm-4",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0
    )

    result = json.loads(response.choices[0].message.content)

    return {"extracted_entities": result.get("entities", [])}

def kg_query_node(state: GraphRAGState) -> dict:
    """阶段3: 在Neo4j中查询实体及其关系"""
    from emergency_agents.graph.kg_service import KGService

    kg_service = KGService(...)

    kg_nodes = []
    kg_relationships = []

    for entity in state["extracted_entities"]:
        # Cypher查询：查找实体节点
        query = """
        MATCH (n)
        WHERE n.name = $name OR $name IN n.aliases
        RETURN n
        LIMIT 5
        """
        nodes = kg_service.execute_cypher(query, name=entity["name"])
        kg_nodes.extend(nodes)

        # Cypher查询：查找节点的1-2跳关系
        if nodes:
            node_id = nodes[0]["id"]
            rel_query = """
            MATCH (n)-[r]->(m)
            WHERE id(n) = $node_id
            RETURN n, r, m
            LIMIT 10
            """
            rels = kg_service.execute_cypher(rel_query, node_id=node_id)
            kg_relationships.extend(rels)

    return {
        "kg_nodes": kg_nodes,
        "kg_relationships": kg_relationships
    }

def graph_reasoning_node(state: GraphRAGState) -> dict:
    """阶段4: 在KG子图上执行推理"""
    from emergency_agents.graph.kg_service import KGService

    kg_service = KGService(...)

    # 4.1 路径查询：找到实体间的最短路径
    reasoning_paths = []
    entities = state["extracted_entities"]

    if len(entities) >= 2:
        for i in range(len(entities) - 1):
            source = entities[i]["name"]
            target = entities[i + 1]["name"]

            path_query = """
            MATCH path = shortestPath(
                (s {name: $source})-[*..3]-(t {name: $target})
            )
            RETURN [node in nodes(path) | node.name] as path
            LIMIT 1
            """
            paths = kg_service.execute_cypher(path_query, source=source, target=target)
            if paths:
                reasoning_paths.append(paths[0]["path"])

    # 4.2 构建局部子图（用于可视化和解释）
    all_node_ids = [n["id"] for n in state["kg_nodes"]]
    subgraph_query = """
    MATCH (n)-[r]-(m)
    WHERE id(n) IN $node_ids AND id(m) IN $node_ids
    RETURN n, r, m
    """
    subgraph_data = kg_service.execute_cypher(subgraph_query, node_ids=all_node_ids)

    return {
        "reasoning_paths": reasoning_paths,
        "subgraph": {"nodes": state["kg_nodes"], "relationships": subgraph_data}
    }

def fusion_node(state: GraphRAGState) -> dict:
    """阶段5: 融合RAG案例 + KG推理结果"""
    from emergency_agents.llm.client import get_openai_client

    # 5.1 构造融合提示词
    rag_summary = f"检索到{len(state['rag_contexts'])}个相似案例"
    kg_summary = f"知识图谱包含{len(state['kg_nodes'])}个相关实体"
    paths_summary = f"发现{len(state['reasoning_paths'])}条推理路径"

    fusion_prompt = f"""基于Graph RAG分析结果生成救援建议：

## RAG历史案例
{chr(10).join([f"- {c['text'][:200]}" for c in state['rag_contexts'][:3]])}

## KG图谱推理
实体：{', '.join([e['name'] for e in state['extracted_entities'][:5]])}
推理路径：{state['reasoning_paths'][0] if state['reasoning_paths'] else '无'}

## 综合分析
请融合历史经验（RAG）和规范知识（KG），生成：
1. 关键风险点（来自KG推理）
2. 推荐措施（来自历史案例）
3. 资源配置（来自KG装备关系）

返回JSON：
{{
  "risks": ["风险1", "风险2"],
  "recommendations": ["建议1", "建议2"],
  "resources": [{{"type": "装备", "name": "...", "source": "KG/RAG"}}]
}}

只返回JSON。"""

    llm = get_openai_client(...)
    response = llm.chat.completions.create(
        model="glm-4",
        messages=[{"role": "user", "content": fusion_prompt}],
        response_format={"type": "json_object"},
        temperature=0.3
    )

    fused_result = json.loads(response.choices[0].message.content)

    # 5.2 添加溯源信息
    fused_result["evidence"] = {
        "rag_cases": [c["text"][:100] for c in state["rag_contexts"]],
        "kg_entities": [e["name"] for e in state["extracted_entities"]],
        "reasoning_paths": state["reasoning_paths"]
    }

    return {"fused_result": fused_result}

# 构建子图
def build_graph_rag_subgraph(
    rag_pipeline,
    kg_service,
    llm_client,
    llm_model: str
) -> CompiledGraph:
    """构建Graph RAG子图"""

    subgraph = StateGraph(GraphRAGState)

    # 注入依赖到节点（闭包方式）
    def make_rag_node():
        def node(state):
            return rag_retrieve_node_graphrag(state)
        return node

    def make_entity_node():
        def node(state):
            # 这里可以访问外部的llm_client
            return entity_extraction_node(state)
        return node

    # 添加节点
    subgraph.add_node("rag_retrieve", make_rag_node())
    subgraph.add_node("extract_entities", make_entity_node())
    subgraph.add_node("kg_query", kg_query_node)
    subgraph.add_node("graph_reasoning", graph_reasoning_node)
    subgraph.add_node("fusion", fusion_node)

    # 添加边（线性流程）
    subgraph.add_edge(START, "rag_retrieve")
    subgraph.add_edge("rag_retrieve", "extract_entities")
    subgraph.add_edge("extract_entities", "kg_query")
    subgraph.add_edge("kg_query", "graph_reasoning")
    subgraph.add_edge("graph_reasoning", "fusion")
    subgraph.add_edge("fusion", END)

    return subgraph.compile()
```

#### 父图集成

```python
# src/emergency_agents/graph/app.py

def build_app(...):
    # ... 现有代码 ...

    # 构建Graph RAG子图
    graph_rag_subgraph = build_graph_rag_subgraph(
        rag_pipeline=rag_pipeline,
        kg_service=kg_service,
        llm_client=llm_client,
        llm_model=cfg.llm_model
    )

    def graph_rag_adapter_node(state: RescueState) -> dict:
        """适配器节点：调用Graph RAG子图"""

        # 1. 父图状态 → 子图状态
        subgraph_input = GraphRAGState(
            query=state.get("prompt", "生成救援方案"),
            disaster_type=state.get("situation", {}).get("disaster_type", "unknown"),
            affected_area=state.get("situation", {}).get("affected_area", ""),
            rag_contexts=[],
            extracted_entities=[],
            kg_nodes=[],
            kg_relationships=[],
            reasoning_paths=[],
            subgraph={},
            fused_result={}
        )

        # 2. 调用子图（同步执行）
        result = graph_rag_subgraph.invoke(subgraph_input)

        # 3. 子图状态 → 父图状态
        return {
            "retrieved_contexts": result["rag_contexts"],
            "kg_hits_count": len(result["kg_nodes"]),
            "rag_case_refs_count": len(result["rag_contexts"]),
            "graph_rag_result": result["fused_result"],
            # 存储完整子图结果供后续审计
            "graph_rag_subgraph_output": result
        }

    # 添加到父图
    graph.add_node("graph_rag", graph_rag_adapter_node)

    # 路由逻辑：复杂场景用Graph RAG，简单场景跳过
    def route_to_graph_rag(state: RescueState) -> str:
        intent = state.get("intent", {}).get("type", "unknown")

        # 只在"方案生成"场景使用Graph RAG
        if intent in ("rescue_task_generate", "plan_generation"):
            return "graph_rag"
        else:
            return "risk_prediction"  # 简单场景直接走原流程

    # 修改边
    # 原来: situation → risk_prediction
    # 现在: situation → (条件)graph_rag → risk_prediction
    graph.add_conditional_edges("situation", route_to_graph_rag, {
        "graph_rag": "graph_rag",
        "risk_prediction": "risk_prediction"
    })
    graph.add_edge("graph_rag", "risk_prediction")
```

### 优势
- ✅ **模块化**: Graph RAG封装为独立子图，易于测试和维护
- ✅ **可复用**: 子图可在多个场景复用（风险预测、方案生成）
- ✅ **可观测**: 子图的每个节点都有独立的checkpoint
- ✅ **灵活路由**: 根据场景复杂度决定是否启用
- ✅ **溯源完整**: `fused_result.evidence`包含RAG+KG完整溯源链

### 注意事项
- ⚠️ 复杂度最高：5个节点，3-4次LLM调用
- ⚠️ 延迟增加2-3秒
- ⚠️ 只在demo演示的"核心场景"启用

---

## 📊 三层架构对比

| 维度 | L1: 库升级 | L2: 节点化 | L3: 子图 |
|------|-----------|-----------|---------|
| **技术** | Hybrid + ColBERT | Self-RAG | Graph RAG |
| **LangGraph改动** | ❌ 无 | ⚠️ +3节点+2条件边 | ⚠️ +子图+适配器节点 |
| **类型安全** | ✅ 完全保留 | ✅ 保留 | ⚠️ 需要状态转换 |
| **可观测性** | ⚠️ 库内部 | ✅ 高（节点级） | ✅ 极高（子图级） |
| **延迟增加** | +50-100ms | +500-1000ms | +2000-3000ms |
| **LLM调用增加** | 0次 | +2次 | +3-4次 |
| **实施时间** | 3天 | 5-7天 | 8-10天 |
| **ROI** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| **风险** | 极低 | 低 | 中 |

---

## 🚀 实施路线图

### Phase 1: 快速见效（Day 1-3）

**目标**: 不改LangGraph，只升级RAG检索精度

```bash
# 1. 安装依赖
pip install ragatouille llama-index-postprocessor-colbert-rerank

# 2. 实现EnhancedRagPipeline
# src/emergency_agents/rag/enhanced_pipe.py

# 3. 替换build_app中的RagPipeline初始化
rag_pipeline = EnhancedRagPipeline(...)

# 4. 测试
pytest tests/test_enhanced_rag.py -v
```

**验收标准**:
- ✅ 现有测试全部通过（零破坏性）
- ✅ 检索精度提升20%+（MRR指标）
- ✅ 延迟<200ms

### Phase 2: Self-RAG增强（Day 4-10）

**目标**: 添加Self-RAG节点，实现智能检索决策

```bash
# 1. 扩展RescueState
# src/emergency_agents/graph/app.py

# 2. 实现3个新节点
def self_rag_router_node(state): ...
def self_rag_retrieve_node(state): ...
def self_rag_evaluator_node(state): ...

# 3. 添加条件边
graph.add_conditional_edges("self_rag_router", route_self_rag, ...)

# 4. 测试
pytest tests/test_self_rag_integration.py -v
```

**验收标准**:
- ✅ 能正确判断是否需要检索（准确率>80%）
- ✅ 评估器能识别低质量检索结果
- ✅ 重检索循环不超过2次

### Phase 3: Graph RAG子图（Day 11-20）

**目标**: 实现KG+RAG深度融合，演示技术亮点

```bash
# 1. 实现子图
# src/emergency_agents/rag/graph_rag.py

# 2. 实现适配器节点
def graph_rag_adapter_node(state): ...

# 3. 添加条件路由
graph.add_conditional_edges("situation", route_to_graph_rag, ...)

# 4. 端到端测试
pytest tests/test_graph_rag_e2e.py -v
```

**验收标准**:
- ✅ 能从RAG案例中提取实体（准确率>70%）
- ✅ 能在Neo4j中找到对应节点（召回率>60%）
- ✅ 融合结果包含KG+RAG溯源链

---

## 💡 最佳实践建议

### 1. 渐进式部署

```python
# 使用feature flag控制功能启用
class RagFeatureFlags:
    ENABLE_HYBRID_SEARCH = os.getenv("RAG_HYBRID", "true") == "true"
    ENABLE_COLBERT = os.getenv("RAG_COLBERT", "true") == "true"
    ENABLE_SELF_RAG = os.getenv("RAG_SELF_RAG", "false") == "true"
    ENABLE_GRAPH_RAG = os.getenv("RAG_GRAPH_RAG", "false") == "true"

# 在build_app中使用
if RagFeatureFlags.ENABLE_SELF_RAG:
    graph.add_node("self_rag_router", ...)
else:
    # 跳过Self-RAG节点，直接连接
    graph.add_edge("situation", "risk_prediction")
```

### 2. 监控指标

```python
# src/emergency_agents/audit/rag_metrics.py

def log_rag_metrics(
    rescue_id: str,
    agent_name: str,
    rag_type: Literal["basic", "hybrid", "self_rag", "graph_rag"],
    retrieval_time_ms: int,
    top_k: int,
    hit_count: int,
    rerank_enabled: bool
):
    """记录RAG检索指标到审计日志"""
    metrics = {
        "timestamp": datetime.utcnow().isoformat(),
        "rescue_id": rescue_id,
        "agent": agent_name,
        "rag_type": rag_type,
        "latency_ms": retrieval_time_ms,
        "top_k": top_k,
        "hits": hit_count,
        "rerank": rerank_enabled
    }

    # 写入PostgreSQL或Prometheus
    logger.info(f"RAG_METRICS: {json.dumps(metrics)}")
```

### 3. A/B测试

```python
# 在不同租户使用不同RAG配置
def get_rag_config(user_id: str) -> dict:
    """根据用户ID返回RAG配置"""

    # 50%用户使用Graph RAG，50%使用基础RAG
    if hash(user_id) % 2 == 0:
        return {
            "enable_graph_rag": True,
            "enable_self_rag": True,
            "enable_colbert": True
        }
    else:
        return {
            "enable_graph_rag": False,
            "enable_self_rag": False,
            "enable_colbert": False
        }
```

### 4. 错误降级

```python
def enhanced_rag_with_fallback(question: str, domain: str) -> list[RagChunk]:
    """带降级策略的RAG检索"""

    try:
        # L3: 尝试Graph RAG
        if RagFeatureFlags.ENABLE_GRAPH_RAG:
            return graph_rag_retrieve(question, domain)
    except Exception as e:
        logger.warning(f"Graph RAG failed: {e}, fallback to Self-RAG")

    try:
        # L2: 降级到Self-RAG
        if RagFeatureFlags.ENABLE_SELF_RAG:
            return self_rag_retrieve(question, domain)
    except Exception as e:
        logger.warning(f"Self-RAG failed: {e}, fallback to Hybrid")

    try:
        # L1: 降级到Hybrid+ColBERT
        return enhanced_rag_pipeline.query(question, domain)
    except Exception as e:
        logger.error(f"Hybrid RAG failed: {e}, fallback to basic")

    # L0: 最后降级到基础RAG
    return basic_rag_pipeline.query(question, domain)
```

---

## 🎯 关键决策总结

### 问题1: 是否需要将RAG实现为LangGraph节点？

**答案**: **分情况**

- ❌ **Hybrid Search + ColBERT**: 不需要，只是检索优化
- ✅ **Self-RAG**: 必须，因为涉及"检索→评估→决策"工作流
- ✅ **Graph RAG**: 必须，因为是复杂多步骤子任务

### 问题2: 状态管理如何设计？

**答案**: **最小化侵入**

```python
# ✅ 推荐：只在需要时添加字段
class RescueState(TypedDict, total=False):
    # ... 现有字段 ...

    # Self-RAG字段（只在启用时使用）
    self_rag_decision: str | None
    self_rag_quality: str | None

    # Graph RAG字段（只在启用时使用）
    graph_rag_result: dict | None
    graph_rag_subgraph_output: dict | None
```

### 问题3: 如何保持类型安全？

**答案**: **使用TypedDict + mypy验证**

```python
# ✅ 所有状态字段都有类型注解
class GraphRAGState(TypedDict, total=False):
    query: str
    rag_contexts: List[Dict[str, Any]]
    extracted_entities: List[Dict[str, str]]
    # ...

# ✅ 节点函数返回类型明确
def entity_extraction_node(state: GraphRAGState) -> dict:
    return {"extracted_entities": [...]}

# ✅ mypy检查
# mypy src/emergency_agents/graph/app.py --strict
```

### 问题4: 性能开销如何控制？

**答案**: **分层启用 + 缓存**

```python
# 1. 分层启用（根据场景复杂度）
if intent == "simple_query":
    use_basic_rag()  # 延迟<100ms
elif intent == "case_retrieval":
    use_hybrid_colbert()  # 延迟<200ms
elif intent == "plan_generation":
    use_graph_rag()  # 延迟<3000ms

# 2. 缓存LLM调用
@lru_cache(maxsize=100)
def entity_extraction_cached(text: str) -> list[dict]:
    return llm_extract_entities(text)
```

---

## ✅ 验收标准

### L1: 库升级验收

- [ ] `EnhancedRagPipeline`通过所有现有单元测试
- [ ] Hybrid检索精度（MRR）提升20%+
- [ ] ColBERT重排序精度（MRR）再提升10%+
- [ ] 总延迟<200ms（p95）

### L2: Self-RAG验收

- [ ] `self_rag_router_node`决策准确率>80%
- [ ] `self_rag_evaluator_node`能识别低质量结果
- [ ] 重检索循环正确终止（最多2次）
- [ ] LangSmith追踪显示完整节点流转

### L3: Graph RAG验收

- [ ] 从RAG案例中提取实体准确率>70%
- [ ] Neo4j实体匹配召回率>60%
- [ ] 融合结果包含KG+RAG完整溯源链
- [ ] 子图可视化正确展示（Mermaid格式）

---

## 📚 参考资源

1. **LangGraph官方文档**
   - Adaptive RAG: https://langchain-ai.github.io/langgraph/tutorials/rag/langgraph_adaptive_rag_local/
   - Subgraphs: https://langchain-ai.github.io/langgraph/how-tos/subgraph/
   - Evaluator-Optimizer: https://langchain-ai.github.io/langgraph/concepts/agentic_concepts/#evaluator-optimizer

2. **RAG技术论文**
   - Self-RAG: https://arxiv.org/abs/2310.11511
   - ColBERT: https://arxiv.org/abs/2004.12832
   - GraphRAG (Microsoft): https://arxiv.org/abs/2404.16130

3. **LlamaIndex文档**
   - Hybrid Retrieval: https://docs.llamaindex.ai/en/stable/examples/retrievers/bm25_retriever/
   - ColBERT Rerank: https://docs.llamaindex.ai/en/stable/examples/node_postprocessor/ColbertRerank/

4. **项目内部文档**
   - 场景化分析: `docs/分析报告/应急救灾场景化RAG技术选型方案.md`
   - 混合检索分析: `docs/分析报告/RAG架构深度分析-LlamaIndex混合检索系统.md`

---

## 🔄 后续演进方向

### 短期（1-2个月）
- [ ] 实现HyDE（假设文档嵌入）用于预案搜索
- [ ] 添加Query Rewrite节点优化查询意图
- [ ] 实现RAG结果的Fact Checking节点

### 中期（3-6个月）
- [ ] 多模态Graph RAG（融合图像、视频）
- [ ] 联邦学习RAG（多地市数据融合）
- [ ] 实时RAG（WebSocket流式返回）

### 长期（6-12个月）
- [ ] Agent-RAG（RAG结果触发Agent行动）
- [ ] 自适应RAG（根据用户反馈自动优化）
- [ ] RAG-as-a-Service（独立微服务）

---

**文档版本**: v1.0
**最后更新**: 2025-10-27
**维护者**: AI应急大脑团队
