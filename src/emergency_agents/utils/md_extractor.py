"""
Markdown侦察方案结构化提取工具

功能：
- 从大模型生成的Markdown侦察方案中提取结构化任务数据
- 使用Instructor库强制LLM输出符合Pydantic模型
- 支持批量提取，降低成本和延迟

技术栈：
- Instructor: 结构化LLM输出（11.7k⭐，300万月下载）
- Pydantic: 数据验证和类型安全
- OpenAI: LLM客户端（兼容GLM等）

使用示例：
```python
from emergency_agents.config import AppConfig
from emergency_agents.utils.md_extractor import ReconPlanExtractor

config = AppConfig.load_from_env()
extractor = ReconPlanExtractor(config)
tasks = extractor.extract_all_tasks(markdown_text)

for task in tasks:
    print(f"任务{task.task_id}: {task.device_name}")
    print(f"  时长: {task.duration_min}分钟")
    print(f"  目标数: {len(task.targets or [])}")
```
"""

import re
import instructor
import structlog
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from openai import OpenAI

from emergency_agents.config import AppConfig

logger = structlog.get_logger(__name__)


# ============ 数据模型 ============


class TargetPoint(BaseModel):
    """侦察目标点"""

    name: str = Field(description="目标点名称，如'新磨村-滑坡监测点A'")
    priority: Optional[float] = Field(
        default=None, description="优先级分数（0-100）", ge=0, le=100
    )
    coordinates: Optional[tuple[float, float]] = Field(
        default=None, description="坐标(经度, 纬度)，如(103.7795, 31.6286)"
    )


class TaskExtract(BaseModel):
    """任务提取结果"""

    task_id: str = Field(description="任务编号，如'任务一'或'任务1'")
    task_type: str = Field(description="任务类型：air(空中)|land(地面)|sea(水上)")
    device_name: str = Field(
        description="设备名称，如'1号态势侦察无人机'或'10号扫图建模无人机'"
    )
    device_id: str = Field(description="设备ID，如'drone-10'或'dog-dv-1'")
    duration_min: Optional[int] = Field(
        default=0,
        description="预计时长（分钟），待命状态可为0或null",
        ge=0,
        le=600
    )

    # 两种模式：点位模式（targets）或区域模式（route_description）
    # 支持字符串列表或对象列表（兼容LLM不同输出格式）
    targets: Optional[List[TargetPoint] | List[str]] = Field(
        default=None, description="侦察目标列表（点位模式），可以是对象列表或字符串列表"
    )
    route_description: Optional[str] = Field(
        default=None, description="侦察路线描述（区域模式），如'姜城古街以东、S302以西'"
    )

    details: Optional[str] = Field(
        default=None, description="侦察详情摘要（200字以内）"
    )
    safety_tips: Optional[str] = Field(default=None, description="安全提示")


class BatchTaskExtract(BaseModel):
    """批量任务提取结果（用于一次提取多个任务）"""

    tasks: List[TaskExtract] = Field(description="提取的任务列表")


# ============ 核心提取器 ============


class ReconPlanExtractor:
    """侦察方案Markdown提取器

    使用Instructor库从Markdown文本中提取结构化任务数据。
    支持批量提取以减少LLM调用次数和成本。
    """

    def __init__(self, config: AppConfig):
        """初始化提取器

        Args:
            config: 应用配置（包含LLM配置）
        """
        # 优先使用侦察专用配置，回退到通用配置
        base_url = config.recon_llm_base_url or config.openai_base_url
        api_key = config.recon_llm_api_key or config.openai_api_key
        model = config.recon_llm_model or config.llm_model or "glm-4-flash"

        # 获取OpenAI客户端
        base_client = OpenAI(
            base_url=base_url,
            api_key=api_key
        )

        # 使用Instructor包装客户端
        self.llm_client = instructor.from_openai(base_client)
        self.model = model

        logger.info(
            "初始化Markdown提取器",
            model=self.model,
            base_url=base_url,
            trace_id=None,
        )

    def extract_all_tasks(self, markdown: str, trace_id: Optional[str] = None) -> List[TaskExtract]:
        """从完整的Markdown侦察方案中提取所有任务

        Args:
            markdown: 完整的Markdown文本
            trace_id: 追踪ID（可选）

        Returns:
            提取的任务列表

        Raises:
            ValueError: 如果Markdown格式无效或提取失败
        """
        logger.info("开始提取侦察方案任务", markdown_length=len(markdown), trace_id=trace_id)

        # 按章节分割Markdown
        sections = self._split_by_sections(markdown)

        if not sections:
            logger.warning("未找到任何侦察方案章节", trace_id=trace_id)
            return []

        logger.info("分割章节完成", section_count=len(sections), trace_id=trace_id)

        # 批量提取所有任务
        all_tasks = []
        for section_name, section_text in sections.items():
            logger.info("提取章节任务", section=section_name, text_length=len(section_text), trace_id=trace_id)

            try:
                tasks = self._extract_tasks_from_section(
                    section_text, section_name, trace_id=trace_id
                )
                all_tasks.extend(tasks)
                logger.info(
                    "章节任务提取成功",
                    section=section_name,
                    task_count=len(tasks),
                    trace_id=trace_id,
                )
            except Exception as e:
                logger.error(
                    "章节任务提取失败",
                    section=section_name,
                    error=str(e),
                    trace_id=trace_id,
                )
                # 继续处理下一个章节，不抛出异常

        logger.info("任务提取完成", total_tasks=len(all_tasks), trace_id=trace_id)
        return all_tasks

    def _split_by_sections(self, markdown: str) -> Dict[str, str]:
        """按侦察类型章节分割Markdown

        识别"一、空中侦察方案"、"二、地面侦察方案"、"三、水上侦察方案"等章节。

        Args:
            markdown: 完整的Markdown文本

        Returns:
            章节字典 {章节名: 章节文本}
        """
        sections = {}

        # 匹配章节标题（支持多种格式）
        # 格式1: ## 一、空中侦察方案
        # 格式2: # 一、空中侦察方案
        # 格式3: 一、空中侦察方案
        pattern = r"(?:^|\n)#{0,3}\s*([一二三四五六七八九十]+、.*?侦察方案)"

        matches = list(re.finditer(pattern, markdown, re.MULTILINE))

        for i, match in enumerate(matches):
            section_title = match.group(1).strip()
            start_pos = match.end()

            # 找到下一个章节的开始位置
            if i + 1 < len(matches):
                end_pos = matches[i + 1].start()
            else:
                end_pos = len(markdown)

            section_text = markdown[start_pos:end_pos].strip()

            # 确定章节类型
            if "空中" in section_title or "空域" in section_title:
                section_type = "air"
            elif "地面" in section_title or "陆地" in section_title:
                section_type = "land"
            elif "水上" in section_title or "水域" in section_title:
                section_type = "sea"
            else:
                section_type = "unknown"

            sections[section_type] = section_text

        return sections

    def _extract_tasks_from_section(
        self, section_text: str, section_type: str, trace_id: Optional[str] = None
    ) -> List[TaskExtract]:
        """从单个章节中提取任务

        使用Instructor库调用LLM进行批量结构化提取。

        Args:
            section_text: 章节文本
            section_type: 章节类型（air/land/sea）
            trace_id: 追踪ID（可选）

        Returns:
            提取的任务列表
        """
        # 构造提取prompt
        prompt = f"""从以下{self._get_section_name(section_type)}侦察方案中提取所有任务的结构化信息。

**原始文本：**
{section_text}

**提取要求：**
1. 识别所有"任务X"或"任务[一二三四五]"等任务块
2. 对每个任务，提取以下信息：
   - task_id: 任务编号（保持原文，如"任务一"）
   - task_type: 固定为"{section_type}"
   - device_name: 设备名称（从"设备配置"中提取并智能生成，如"1号态势侦察无人机"）
   - device_id: 设备ID（从括号中的ID提取，如"drone-10"）
   - duration_min: 预计时长（分钟数，待命/预备状态设为0或null）
   - targets: 侦察目标列表（支持两种格式）
     * 完整格式：{{"name": "目标名", "priority": 90.0, "coordinates": (103.78, 31.62)}}
     * 简化格式：["目标名1", "目标名2", ...]  ← 推荐使用，更简洁
   - route_description: 侦察路线描述（如果是区域描述而非点位列表）
   - details: 侦察详情摘要（可选，不超过200字）
   - safety_tips: 安全提示（可选）

3. 注意事项：
   - 设备名称生成规则：从ID中提取编号 + 设备类型
     例如：(ID: drone-10) → "10号态势侦察无人机"
     例如：(ID: dog-dv-1) → "dv-1号医疗救援机器狗"
   - 时长转换：
     "90分钟" → 90
     "2小时" → 120
     "1小时30分钟" → 90
     "待命" / "预备" → 0 或 null
   - targets优先使用简化格式（字符串数组），除非有明确的优先级/坐标数据
   - 如果既有目标列表又有路线描述，优先填充targets

**输出格式：**
严格按照Pydantic模型格式输出JSON，包含所有识别到的任务。
"""

        try:
            # 调用Instructor进行结构化提取
            result = self.llm_client.chat.completions.create(
                model=self.model,
                response_model=BatchTaskExtract,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,  # 确保稳定性
                max_retries=0,  # 禁用自动重试，避免超时累积（修改：1→0）
                timeout=180.0,   # 增加到180秒，适应GLM-4.6的推理速度（修改：120→180）
            )

            return result.tasks

        except Exception as e:
            error_msg = str(e)

            # 增强错误日志
            logger.error(
                "LLM结构化提取失败",
                section_type=section_type,
                section_length=len(section_text),
                model=self.model,
                error=error_msg,
                error_type=type(e).__name__,
                trace_id=trace_id,
            )

            # 友好的错误消息
            if "500" in error_msg or "Internal Server Error" in error_msg:
                raise ValueError(
                    f"LLM服务暂时不可用（500错误），请稍后重试。"
                    f"章节：{self._get_section_name(section_type)}，"
                    f"文本长度：{len(section_text)}字节"
                )
            elif "timeout" in error_msg.lower():
                raise ValueError(
                    f"LLM处理超时（>120秒），文本可能过长。"
                    f"章节：{self._get_section_name(section_type)}，"
                    f"文本长度：{len(section_text)}字节"
                )
            elif "rate" in error_msg.lower() or "limit" in error_msg.lower():
                raise ValueError(
                    f"LLM请求频率限制，请稍后重试。"
                    f"章节：{self._get_section_name(section_type)}"
                )
            else:
                raise ValueError(f"任务提取失败: {error_msg}")

    def _get_section_name(self, section_type: str) -> str:
        """获取章节中文名称"""
        mapping = {
            "air": "空中",
            "land": "地面",
            "sea": "水上",
            "unknown": "未知",
        }
        return mapping.get(section_type, section_type)
