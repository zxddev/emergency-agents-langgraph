from __future__ import annotations  # 启用前向注解

import socket  # 用于检测端口连通性
from typing import Dict  # 引入类型提示
from urllib.parse import urlparse  # 解析地址

import httpx  # HTTP 客户端
import structlog  # 结构化日志

from emergency_agents.config import AppConfig  # 引入应用配置
from emergency_agents.memory.mem0_facade import Mem0Config  # 引入 Mem0 配置

logger = structlog.get_logger(__name__)  # 初始化日志器


def _check_qdrant(mem_cfg: Mem0Config, embedding_dim: int) -> None:
    """校验 Qdrant 集合是否存在且维度匹配。"""
    base_url: str = mem_cfg.qdrant_url.rstrip("/")  # 清理尾部斜杠
    endpoint: str = f"{base_url}/collections/{mem_cfg.qdrant_collection}"  # 拼接查询路径
    timeout = httpx.Timeout(connect=3.0, read=3.0, write=3.0, pool=3.0)  # 构建超时配置
    with httpx.Client(timeout=timeout, verify=False) as client:  # 创建同步客户端
        response = client.get(endpoint)  # 发起 GET 请求
    if response.status_code != 200:  # 检查返回码
        raise RuntimeError(f"Qdrant 集合检查失败: HTTP {response.status_code}")  # 抛出错误
    payload: Dict[str, object] = response.json()  # 解析响应
    result = payload.get("result")  # 获取结果域
    if not isinstance(result, dict):  # 校验结构
        raise RuntimeError("Qdrant 集合结果格式异常")  # 抛出错误
    config = result.get("config")  # 读取配置域
    params = isinstance(config, dict) and config.get("params") or None  # 读取参数
    vectors = isinstance(params, dict) and params.get("vectors") or None  # 读取向量配置
    if not isinstance(vectors, dict):  # 验证结构
        raise RuntimeError("Qdrant 集合缺少向量配置")  # 抛出错误
    size = vectors.get("size")  # 获取维度
    if int(size) != embedding_dim:  # 比对维度
        raise RuntimeError(f"Qdrant 维度不匹配: {size} != {embedding_dim}")  # 抛出错误
    logger.info("startup_check_qdrant_ok", collection=mem_cfg.qdrant_collection)  # 记录成功


def _check_neo4j(mem_cfg: Mem0Config) -> None:
    """校验 Neo4j 端口连通性。"""
    parsed = urlparse(mem_cfg.neo4j_uri)  # 解析 URI
    if parsed.hostname is None:  # 校验主机
        raise RuntimeError("Neo4j URI 缺少主机名")  # 抛出错误
    host: str = parsed.hostname  # 记录主机
    port: int = parsed.port or 7687  # 解析端口
    with socket.create_connection((host, port), timeout=3.0):  # 建立连接
        logger.info("startup_check_neo4j_ok", host=host, port=port)  # 记录成功


def _check_llm_endpoints(cfg: AppConfig) -> None:
    """校验 LLM 端点配置是否有效。"""
    if not cfg.llm_endpoints:  # 确保存在端点
        raise RuntimeError("未配置任何 LLM 端点")  # 抛出错误
    for endpoint in cfg.llm_endpoints:  # 遍历端点
        if not endpoint.api_key or "dummy" in endpoint.api_key:  # 检查 key
            raise RuntimeError(f"端点 {endpoint.name} 缺少有效 API Key")  # 抛出错误
    logger.info("startup_check_llm_ok", endpoints=[e.name for e in cfg.llm_endpoints])  # 记录成功


def run_startup_self_check(cfg: AppConfig, mem_cfg: Mem0Config, *, enable_mem0: bool) -> None:
    """运行启动自检。"""
    _check_llm_endpoints(cfg)  # 检查 LLM 端点
    if enable_mem0:  # 判断是否启用 Mem0
        _check_qdrant(mem_cfg, cfg.embedding_dim)  # 校验 Qdrant
        _check_neo4j(mem_cfg)  # 校验 Neo4j
