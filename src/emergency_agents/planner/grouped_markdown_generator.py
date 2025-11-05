"""
分组Markdown生成器

功能：
- 按设备环境类型分组（air/land/sea）
- 并行调用LLM生成3个章节
- 拼接完整Markdown报告

核心优化：
1. 分组：将分配结果按env_type分为 air/land/sea 三组
2. 并行LLM调用：每组独立调用LLM生成Markdown（3个线程）
3. 章节拼接：按顺序拼接为完整Markdown

性能目标：
- 3个章节并行调用：<45秒
- 每个章节：<30秒
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional
from uuid import UUID

from openai import OpenAI
import structlog

logger = structlog.get_logger(__name__)


# ============ 章节标题映射 ============


SECTION_TITLES = {
    "air": "一、空中侦察方案",
    "land": "二、地面侦察方案",
    "sea": "三、水上侦察方案"
}

ENV_TYPE_NAMES = {
    "air": "空中",
    "land": "地面",
    "sea": "水上"
}

SEVERITY_NAMES = {
    "critical": "极危险",
    "high": "高危",
    "medium": "中等",
    "low": "低危"
}


# ============ 分组Markdown生成器 ============


class GroupedMarkdownGenerator:
    """分组Markdown生成器"""

    def __init__(self, llm_client: OpenAI, llm_model: str):
        """
        初始化生成器

        参数：
            llm_client: OpenAI客户端实例
            llm_model: 模型名称（如 'glm-4.6'）
        """
        self.llm_client = llm_client
        self.llm_model = llm_model
        self.logger = logger.bind(model=llm_model)

    def generate(
        self,
        allocation: Dict[str, List[str]],  # device_id -> target_ids
        devices: List[Dict[str, Any]],
        targets: List[Dict[str, Any]],
        disaster_info: Dict[str, Any],
        command_center: Dict[str, float],
        trace_id: str = None
    ) -> str:
        """
        生成按设备类型分组的Markdown报告

        流程：
        1. 按env_type分组设备和任务
        2. 并行调用LLM生成3个章节
        3. 拼接完整Markdown

        参数：
            allocation: 设备-目标分配结果 {device_id: [target_ids]}
            devices: 设备列表
            targets: 目标列表
            disaster_info: 灾情信息
            command_center: 指挥中心坐标
            trace_id: 追踪ID

        返回：
            完整的Markdown文本
        """
        start_time = time.time()

        self.logger.info(
            "开始分组Markdown生成",
            device_count=len(devices),
            target_count=len(targets),
            trace_id=trace_id
        )

        # 1. 按env_type分组
        air_group = self._group_by_env_type(allocation, devices, targets, "air")
        land_group = self._group_by_env_type(allocation, devices, targets, "land")
        sea_group = self._group_by_env_type(allocation, devices, targets, "sea")

        # 2. 并行生成章节（使用ThreadPoolExecutor）
        sections = {}
        futures_map = {}

        with ThreadPoolExecutor(max_workers=3, thread_name_prefix="markdown_gen") as executor:
            if air_group["devices"]:
                future_air = executor.submit(
                    self._generate_section,
                    "air",
                    air_group,
                    disaster_info,
                    command_center,
                    trace_id
                )
                futures_map[future_air] = "air"

            if land_group["devices"]:
                future_land = executor.submit(
                    self._generate_section,
                    "land",
                    land_group,
                    disaster_info,
                    command_center,
                    trace_id
                )
                futures_map[future_land] = "land"

            if sea_group["devices"]:
                future_sea = executor.submit(
                    self._generate_section,
                    "sea",
                    sea_group,
                    disaster_info,
                    command_center,
                    trace_id
                )
                futures_map[future_sea] = "sea"

            # 收集结果（增强超时处理）
            try:
                for future in as_completed(futures_map.keys(), timeout=300):  # 300秒超时
                    env_type = futures_map[future]
                    try:
                        markdown = future.result(timeout=5)  # 已经完成，只需取结果
                        sections[env_type] = markdown
                        self.logger.info(
                            f"{ENV_TYPE_NAMES[env_type]}章节生成成功",
                            env_type=env_type,
                            length=len(markdown),
                            trace_id=trace_id
                        )
                    except Exception as e:
                        self.logger.error(
                            f"{ENV_TYPE_NAMES[env_type]}章节生成失败",
                            env_type=env_type,
                            error=str(e),
                            trace_id=trace_id
                        )
                        sections[env_type] = self._generate_fallback_section(env_type, str(e))
            except TimeoutError as e:
                # 处理整体超时：为所有未完成的future生成降级内容
                self.logger.warning(
                    "部分章节生成超时，使用降级方案",
                    timeout_seconds=300,
                    trace_id=trace_id
                )
                for future, env_type in futures_map.items():
                    if env_type not in sections:
                        # 这个future还没完成，生成降级内容
                        sections[env_type] = self._generate_fallback_section(
                            env_type,
                            f"生成超时（>300秒），已取消该章节生成"
                        )

        # 3. 拼接Markdown
        full_markdown = self._assemble_markdown(
            sections,
            disaster_info,
            command_center,
            air_group,
            land_group,
            sea_group
        )

        elapsed_seconds = time.time() - start_time
        self.logger.info(
            "分组Markdown生成完成",
            sections_count=len(sections),
            total_length=len(full_markdown),
            elapsed_seconds=round(elapsed_seconds, 2),
            trace_id=trace_id
        )

        return full_markdown

    def _group_by_env_type(
        self,
        allocation: Dict[str, List[str]],
        devices: List[Dict[str, Any]],
        targets: List[Dict[str, Any]],
        env_type: str
    ) -> Dict[str, Any]:
        """
        按环境类型分组设备和任务

        返回：
            {
                "env_type": "air",
                "devices": [device_dict, ...],
                "allocation": {device_id: [target_dicts]},
                "target_count": 10
            }
        """
        # 创建设备和目标的映射
        device_map = {str(d["id"]): d for d in devices}
        target_map = {str(t["id"]): t for t in targets}

        # 过滤该环境类型的设备
        filtered_devices = []
        filtered_allocation = {}

        for device_id, target_ids in allocation.items():
            device = device_map.get(device_id)
            if not device:
                continue

            device_env = device.get("env_type", "").lower()

            # 匹配环境类型
            if env_type == "air" and device_env == "air":
                filtered_devices.append(device)
                # 将target_ids转换为target对象
                filtered_allocation[device_id] = [
                    target_map[tid] for tid in target_ids if tid in target_map
                ]
            elif env_type == "land" and device_env == "land":
                filtered_devices.append(device)
                filtered_allocation[device_id] = [
                    target_map[tid] for tid in target_ids if tid in target_map
                ]
            elif env_type == "sea" and device_env in ["sea", "water"]:
                filtered_devices.append(device)
                filtered_allocation[device_id] = [
                    target_map[tid] for tid in target_ids if tid in target_map
                ]

        total_targets = sum(len(targets) for targets in filtered_allocation.values())

        return {
            "env_type": env_type,
            "devices": filtered_devices,
            "allocation": filtered_allocation,
            "target_count": total_targets
        }

    def _generate_section(
        self,
        env_type: str,
        group_data: Dict[str, Any],
        disaster_info: Dict[str, Any],
        command_center: Dict[str, float],
        trace_id: str = None
    ) -> str:
        """
        生成单个章节的Markdown（空中/地面/水上）

        参数：
            env_type: 环境类型（'air' / 'land' / 'sea'）
            group_data: 分组数据（devices, allocation, target_count）
            disaster_info: 灾情信息
            command_center: 指挥中心坐标
            trace_id: 追踪ID

        返回：
            Markdown文本（包含章节标题和任务列表）
        """
        start_time = time.time()

        self.logger.info(
            f"开始生成{ENV_TYPE_NAMES[env_type]}章节",
            env_type=env_type,
            device_count=len(group_data["devices"]),
            target_count=group_data["target_count"],
            trace_id=trace_id
        )

        if not group_data["devices"]:
            return ""

        # 构造Prompt
        prompt = self._build_section_prompt(
            env_type,
            group_data,
            disaster_info,
            command_center
        )

        # 调用LLM（添加显式300秒超时）
        try:
            response = self.llm_client.chat.completions.create(
                model=self.llm_model,
                messages=[
                    {
                        "role": "system",
                        "content": "你是应急救援侦察方案专家，擅长生成清晰专业的任务报告。"
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,
                max_tokens=16000,  # GLM-4.6支持最大128K，设置16K足够容纳完整输出
                timeout=300  # 显式设置300秒超时，与ThreadPoolExecutor一致
            )

            markdown = response.choices[0].message.content.strip()

            elapsed_ms = int((time.time() - start_time) * 1000)
            self.logger.info(
                f"{ENV_TYPE_NAMES[env_type]}章节LLM调用成功",
                env_type=env_type,
                elapsed_ms=elapsed_ms,
                output_length=len(markdown),
                trace_id=trace_id
            )

            return markdown

        except Exception as e:
            elapsed_ms = int((time.time() - start_time) * 1000)
            self.logger.error(
                f"{ENV_TYPE_NAMES[env_type]}章节LLM调用失败",
                env_type=env_type,
                elapsed_ms=elapsed_ms,
                error=str(e),
                trace_id=trace_id
            )
            raise

    def _build_section_prompt(
        self,
        env_type: str,
        group_data: Dict[str, Any],
        disaster_info: Dict[str, Any],
        command_center: Dict[str, float]
    ) -> str:
        """
        构造分组章节的LLM Prompt

        输出示例：
        ## 一、空中侦察方案

        ### 任务一：重灾区扫图建模
        **设备配置**：扫图建模无人机（drone-A1）
        - 能力：激光雷达、多光谱传感器

        **侦察目标**：
        1. 水西村重灾区（优先级：95）
        2. 茂县县城（优先级：92）

        **侦察详情**：
        从指挥中心起飞，首先对水西村进行三维扫描建模...

        **预计时长**：60分钟

        **安全提示**：
        - 注意高压线和山体遮挡
        - 风速>8m/s时停止作业
        """
        # 转换严重程度为中文
        severity_en = disaster_info.get('severity', 'unknown').lower()
        severity_cn = SEVERITY_NAMES.get(severity_en, '未知')

        prompt_parts = [
            f"**任务类型**：{SECTION_TITLES[env_type]}",
            f"**灾害信息**：{disaster_info.get('disaster_type', '未知')} - {severity_cn}级",
            f"**指挥中心**：({command_center.get('lon', 0)}, {command_center.get('lat', 0)})",
            "",
            "**可用设备及分配任务**：",
        ]

        # 列出该环境类型的所有设备和分配的目标
        for idx, device in enumerate(group_data["devices"], start=1):
            device_id = str(device["id"])
            target_objects = group_data["allocation"].get(device_id, [])

            prompt_parts.append(f"设备{idx}：{device.get('name', 'unknown')} (ID: {device_id})")
            prompt_parts.append(f"  类型：{device.get('device_type', 'unknown')}")
            prompt_parts.append(f"  能力：{', '.join(device.get('capabilities', ['无']))}")
            prompt_parts.append(f"  分配目标（共{len(target_objects)}个）：")

            for t in target_objects:
                prompt_parts.append(
                    f"    - {t.get('name', 'unknown')} "
                    f"(优先级: {t.get('priority', 0)}, "
                    f"危险等级: {t.get('hazard_level', 'unknown')}, "
                    f"坐标: {t.get('lon', 0)}, {t.get('lat', 0)})"
                )
            prompt_parts.append("")

        prompt_parts.append("**输出要求**：")
        prompt_parts.append(f"1. 生成章节标题（{SECTION_TITLES[env_type]}）")
        prompt_parts.append("2. 为每个设备生成一个任务段落（### 任务一、### 任务二...）")
        prompt_parts.append("3. 每个任务包含：")
        prompt_parts.append("   - **设备配置**：设备名称和能力描述")
        prompt_parts.append("   - **侦察目标**：列出所有目标（序号+名称+优先级）")
        prompt_parts.append("   - **侦察详情**：详细的侦察路线和方法（100-200字）")
        prompt_parts.append("   - **预计时长**：估算任务耗时（分钟）")
        prompt_parts.append("   - **安全提示**：针对该环境和目标的安全注意事项")
        prompt_parts.append("4. 使用Markdown格式，语言流畅专业")
        prompt_parts.append("5. 不要包含```markdown标记，直接输出Markdown文本")

        return "\n".join(prompt_parts)

    def _generate_fallback_section(self, env_type: str, error_msg: str) -> str:
        """生成降级章节（LLM调用失败时）"""
        return f"""## {SECTION_TITLES[env_type]}

（生成失败：{error_msg}）

请手动补充该章节内容。
"""

    def _assemble_markdown(
        self,
        sections: Dict[str, str],
        disaster_info: Dict[str, Any],
        command_center: Dict[str, float],
        air_group: Dict[str, Any],
        land_group: Dict[str, Any],
        sea_group: Dict[str, Any]
    ) -> str:
        """
        拼接完整Markdown报告

        结构：
        # 标题
        概述段落

        ## 一、空中侦察方案
        ...

        ## 二、地面侦察方案
        ...

        ## 三、水上侦察方案
        ...

        ## 四、数据整合与通信
        ...
        """
        parts = []

        # 1. 标题
        disaster_type_cn = {
            "flood": "洪水",
            "earthquake": "地震",
            "landslide": "山体滑坡",
            "chemical_leak": "化工泄露"
        }.get(disaster_info.get("disaster_type", "").lower(), disaster_info.get("disaster_type", "未知灾害"))

        parts.append(f"# {disaster_type_cn}灾害侦察方案")
        parts.append("")

        # 2. 概述
        total_devices = len(air_group["devices"]) + len(land_group["devices"]) + len(sea_group["devices"])
        total_targets = air_group["target_count"] + land_group["target_count"] + sea_group["target_count"]

        parts.append("## 概述")
        parts.append("")
        parts.append(f"**灾情信息**：{disaster_type_cn}灾害，严重程度：{disaster_info.get('severity', '未知')}")
        parts.append(f"**指挥中心位置**：({command_center.get('lon', 0)}, {command_center.get('lat', 0)})")
        parts.append(f"**配备设备**：共{total_devices}台（空中{len(air_group['devices'])}台、地面{len(land_group['devices'])}台、水上{len(sea_group['devices'])}台）")
        parts.append(f"**侦察目标**：共{total_targets}个优先目标")
        parts.append("")
        parts.append("**整体任务目标**：全面侦察灾区情况，采集多维度数据，为救援决策提供依据。")
        parts.append("")

        # 3. 拼接各章节（按air/land/sea顺序）
        for env_type in ["air", "land", "sea"]:
            if env_type in sections and sections[env_type]:
                parts.append(sections[env_type])
                parts.append("")

        # 4. 数据整合与通信章节
        parts.append("## 四、数据整合与通信")
        parts.append("")
        parts.append("**数据回传**：")
        parts.append("- 空中侦察数据：三维点云、正射影像、热成像数据")
        parts.append("- 地面侦察数据：建筑损毁照片、道路受阻信息、人员搜救反馈")
        parts.append("- 水上侦察数据：水域水位、水质检测、漂浮物分布")
        parts.append("")
        parts.append("**数据汇总**：所有数据实时回传至指挥中心，通过GIS平台整合展示。")
        parts.append("")
        parts.append("**通信保障**：")
        parts.append("- 主链路：4G/5G网络")
        parts.append("- 备用链路：卫星通信")
        parts.append("- 紧急情况：现场手持电台")

        return "\n".join(parts)
