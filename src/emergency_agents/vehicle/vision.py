#!/usr/bin/env python3
# Copyright 2025 msq
"""
视觉分析服务 - 基于GLM-4V-Plus的无人机图像分析

核心功能：
- 人员/车辆检测与计数
- 建筑物损毁评估
- 道路通行状态分析
- 危险等级评定 (L0/L1/L2/L3)

技术栈：
- GLM-4V-Plus (vLLM部署在H100 GPU#1)
- 结构化JSON输出
- 毫秒级性能监控
"""
from __future__ import annotations

import base64
import json
import logging
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, Any, Optional, List

import httpx

logger = logging.getLogger(__name__)


class DangerLevel(str, Enum):
    """危险等级枚举"""
    L0 = "L0"  # 正常 - 无危险
    L1 = "L1"  # 低危 - 需要关注
    L2 = "L2"  # 中危 - 需要预案
    L3 = "L3"  # 高危 - 立即处置


@dataclass
class PersonDetection:
    """人员检测结果"""
    count: int
    positions: List[Dict[str, float]]  # [{"x": 0.5, "y": 0.3, "confidence": 0.95}]
    activities: List[str]  # ["站立", "行走", "躺卧"]


@dataclass
class VehicleDetection:
    """车辆检测结果"""
    total_count: int
    by_type: Dict[str, int]  # {"小汽车": 3, "卡车": 1, "救护车": 1}
    positions: List[Dict[str, Any]]


@dataclass
class BuildingAssessment:
    """建筑物评估结果"""
    total_buildings: int
    damaged_count: int
    damage_levels: Dict[str, int]  # {"完好": 5, "轻度": 3, "中度": 2, "严重": 1}
    collapse_risk: bool


@dataclass
class RoadStatus:
    """道路状态评估"""
    passable: bool
    blocked_sections: List[str]
    obstacles: List[str]  # ["倒塌建筑物", "车辆堵塞"]


@dataclass
class VisionAnalysisResult:
    """视觉分析完整结果"""
    danger_level: DangerLevel
    persons: PersonDetection
    vehicles: VehicleDetection
    buildings: BuildingAssessment
    roads: RoadStatus
    hazards: List[str]  # 识别到的危险因素
    recommendations: List[str]  # 建议的行动

    # 性能指标
    latency_ms: float
    model_name: str
    confidence_score: float

    # 元数据
    image_size: Optional[tuple] = None
    analysis_time: Optional[str] = None


class VisionAnalyzer:
    """GLM-4V视觉分析器

    使用方法：
        analyzer = VisionAnalyzer(vllm_url="http://192.168.31.40:8001/v1")
        result = await analyzer.analyze_drone_image("path/to/image.jpg")
        print(f"危险等级: {result.danger_level}")
        print(f"检测到 {result.persons.count} 人, {result.vehicles.total_count} 辆车")
    """

    def __init__(
        self,
        vllm_url: str = "http://localhost:8001/v1",
        model_name: str = "glm-4v-plus",
        *,
        api_key: str | None = None,
        timeout: float = 30.0,
        temperature: float = 0.1,
    ):
        """初始化视觉分析器

        Args:
            vllm_url: vLLM服务地址 (GLM-4V-Plus on H100 #1)
            model_name: 模型名称
            timeout: 超时时间（秒）
            temperature: LLM温度参数（建议0.1保证稳定性）
        """
        self.vllm_url = vllm_url.rstrip("/")
        self.model_name = model_name
        self.api_key = api_key
        self.timeout = timeout
        self.temperature = temperature
        headers: dict[str, str] = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self.client = httpx.AsyncClient(timeout=timeout, trust_env=False, headers=headers)

        logger.info(
            f"VisionAnalyzer initialized: vllm_url={vllm_url}, "
            f"model={model_name}, timeout={timeout}s"
        )

    async def analyze_drone_image(
        self,
        image_path: Optional[str] = None,
        image_base64: Optional[str] = None,
    ) -> VisionAnalysisResult:
        """分析无人机航拍图像

        Args:
            image_path: 图像文件路径（与image_base64二选一）
            image_base64: Base64编码的图像数据（与image_path二选一）

        Returns:
            VisionAnalysisResult: 结构化分析结果

        Raises:
            ValueError: 参数错误
            httpx.HTTPError: 网络或API错误
        """
        start_time = time.time()

        # 准备图像数据
        if image_path:
            img_b64 = self._encode_image_file(image_path)
        elif image_base64:
            img_b64 = image_base64
        else:
            raise ValueError("必须提供 image_path 或 image_base64 之一")

        # 构建提示词（应急救援专用）
        prompt = self._build_analysis_prompt()

        # 调用GLM-4V API
        try:
            raw_result = await self._call_vllm_api(img_b64, prompt)

            # 解析结构化输出
            structured = self._parse_llm_output(raw_result)

            # 构建返回结果
            latency_ms = (time.time() - start_time) * 1000
            result = self._build_result(structured, latency_ms)

            logger.info(
                f"Vision analysis completed in {latency_ms:.0f}ms: "
                f"danger={result.danger_level}, persons={result.persons.count}, "
                f"vehicles={result.vehicles.total_count}"
            )

            return result

        except Exception as e:
            logger.error(f"Vision analysis failed: {e}", exc_info=True)
            raise

    def _encode_image_file(self, image_path: str) -> str:
        """将图像文件编码为Base64"""
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"图像文件不存在: {image_path}")

        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    def _build_analysis_prompt(self) -> str:
        """构建应急救援场景的分析提示词"""
        return """作为应急救援专家，请分析这张无人机航拍图，识别以下信息：

1. **人员情况**
   - 统计人员数量
   - 标注大致位置（归一化坐标0-1）
   - 识别活动状态（站立/行走/躺卧/求救）

2. **车辆情况**
   - 统计各类型车辆数量（小汽车/卡车/救护车/消防车）
   - 标注位置

3. **建筑物状况**
   - 统计建筑物总数
   - 评估损毁情况（完好/轻度/中度/严重/倒塌）
   - 判断是否有倒塌风险

4. **道路状态**
   - 判断是否可通行
   - 识别阻塞路段
   - 标注障碍物

5. **危险因素**
   - 识别火灾/烟雾/化学泄漏/塌方等
   - 评估危险程度

6. **综合危险等级**
   - L0: 正常，无明显危险
   - L1: 低危，需要关注
   - L2: 中危，需要准备预案
   - L3: 高危，立即处置

**请严格按以下JSON格式返回，不要有任何其他文字：**

```json
{
  "danger_level": "L0/L1/L2/L3",
  "persons": {
    "count": 0,
    "positions": [{"x": 0.5, "y": 0.3, "confidence": 0.95, "activity": "站立"}],
    "activities": ["站立", "行走"]
  },
  "vehicles": {
    "total_count": 0,
    "by_type": {"小汽车": 2, "卡车": 1},
    "positions": [{"x": 0.2, "y": 0.7, "type": "救护车"}]
  },
  "buildings": {
    "total_buildings": 10,
    "damaged_count": 3,
    "damage_levels": {"完好": 7, "轻度": 2, "中度": 1},
    "collapse_risk": false
  },
  "roads": {
    "passable": true,
    "blocked_sections": [],
    "obstacles": []
  },
  "hazards": ["火灾", "建筑倒塌"],
  "recommendations": ["派遣消防队", "疏散附近居民"],
  "confidence_score": 0.85
}
```

如果某些信息无法确定，使用null或空数组。"""

    async def _call_vllm_api(self, image_b64: str, prompt: str) -> str:
        """调用vLLM OpenAI兼容API"""
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_b64}"
                        },
                    },
                    {
                        "type": "text",
                        "text": prompt,
                    },
                ],
            }
        ]

        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": 2048,
        }

        response = await self.client.post(
            f"{self.vllm_url}/chat/completions",
            json=payload,
        )
        response.raise_for_status()

        data = response.json()
        return data["choices"][0]["message"]["content"]

    def _parse_llm_output(self, raw_output: str) -> Dict[str, Any]:
        """解析LLM输出的JSON（带容错）"""
        # 尝试提取JSON代码块
        if "```json" in raw_output:
            import re
            match = re.search(r"```json\n(.*?)\n```", raw_output, re.DOTALL)
            if match:
                json_str = match.group(1)
            else:
                json_str = raw_output
        else:
            json_str = raw_output

        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing failed: {e}\nRaw output: {raw_output[:500]}")
            # 返回安全的默认值
            return {
                "danger_level": "L0",
                "persons": {"count": 0, "positions": [], "activities": []},
                "vehicles": {"total_count": 0, "by_type": {}, "positions": []},
                "buildings": {
                    "total_buildings": 0,
                    "damaged_count": 0,
                    "damage_levels": {},
                    "collapse_risk": False,
                },
                "roads": {"passable": True, "blocked_sections": [], "obstacles": []},
                "hazards": [],
                "recommendations": ["数据解析失败，建议人工核查"],
                "confidence_score": 0.0,
            }

    def _build_result(
        self, structured: Dict[str, Any], latency_ms: float
    ) -> VisionAnalysisResult:
        """构建VisionAnalysisResult对象"""
        return VisionAnalysisResult(
            danger_level=DangerLevel(structured.get("danger_level", "L0")),
            persons=PersonDetection(
                count=structured.get("persons", {}).get("count", 0),
                positions=structured.get("persons", {}).get("positions", []),
                activities=structured.get("persons", {}).get("activities", []),
            ),
            vehicles=VehicleDetection(
                total_count=structured.get("vehicles", {}).get("total_count", 0),
                by_type=structured.get("vehicles", {}).get("by_type", {}),
                positions=structured.get("vehicles", {}).get("positions", []),
            ),
            buildings=BuildingAssessment(
                total_buildings=structured.get("buildings", {}).get("total_buildings", 0),
                damaged_count=structured.get("buildings", {}).get("damaged_count", 0),
                damage_levels=structured.get("buildings", {}).get("damage_levels", {}),
                collapse_risk=structured.get("buildings", {}).get("collapse_risk", False),
            ),
            roads=RoadStatus(
                passable=structured.get("roads", {}).get("passable", True),
                blocked_sections=structured.get("roads", {}).get("blocked_sections", []),
                obstacles=structured.get("roads", {}).get("obstacles", []),
            ),
            hazards=structured.get("hazards", []),
            recommendations=structured.get("recommendations", []),
            latency_ms=latency_ms,
            model_name=self.model_name,
            confidence_score=structured.get("confidence_score", 0.0),
        )

    async def close(self):
        """关闭HTTP客户端"""
        await self.client.aclose()
