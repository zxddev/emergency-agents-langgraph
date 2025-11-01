from __future__ import annotations

import json
from typing import Any, Dict, Iterable


def _format_section(title: str, lines: Iterable[str]) -> str:
    content = "\n".join(line for line in lines if line)
    if not content.strip():
        return ""
    return f"{title}\n{content.strip()}\n"


def build_rescue_assessment_prompt(payload: Dict[str, Any]) -> str:
    """构造汇报提示词。

    Args:
        payload: 已序列化的灾情数据，键名需与 API 模型保持一致。

    Returns:
        供大模型使用的完整提示词。
    """

    json_blob = json.dumps(payload, ensure_ascii=False, indent=2)
    header = (
        "你现在是“前突侦察指挥组”负责人，需要以极度专业、正式且简洁有力的口吻，"
        "向“省级应急指挥大厅”进行灾情汇报。\n"
        "核心要求：\n"
        "1. 所有时间、地名、数字、百分比、强度级别以及部队、装备名称必须与原始数据保持逐字一致，禁止自行修改或推测。\n"
        "2. 若某个字段缺失或无法确定，必须在对应位置写出“待补充”，不得掩盖缺口。\n"
        "3. 汇报结构需涵盖示例模板中的全部章节，并可根据数据添加必要的小节，但禁止删减主章节。\n"
        "4. 语气要体现当前战时紧迫感，条理清晰，逻辑严密，便于指挥部快速决策。\n"
        "5. 输出内容使用 Markdown，标题层级与项目符号必须规范，重点信息可加粗。\n"
        "6. 如存在次生灾害风险或增援需求，必须在相应章节明确提请指挥部决策。\n"
    )

    template = _format_section(
        "必须生成的章节：",
        [
            "一、当前灾情初步评估 —— 需要列出人员伤亡、基础设施受损、四断情况、农业与经济损失等。",
            "二、组织指挥 —— 描述现有组织体系、工作组设置、现场指挥机制。",
            "三、救援力量部署与任务分工 —— 列出已投入力量、各自任务，以及对军队、武警、专业队伍、公安、医疗、工程等的部署建议。",
            "四、次生灾害预防与安全措施 —— 报告余震、降雨、滑坡等风险与拟采取的防范举措。",
            "五、通信与信息保障 —— 说明通信恢复进展、信息报送频率等。",
            "六、物资调配与运输保障 —— 概述已到位物资与仍需协调的物资种类、数量及时间节点。",
            "七、救援力量自身保障 —— 强调救援人员轮换、补给、医疗保障安排。",
            "结尾需以“前突侦察指挥组”落款，并保留报告日期。",
        ],
    )

    guidance = _format_section(
        "数据载荷（禁止篡改任何字段）：",
        [f"```json\n{json_blob}\n```"],
    )

    writing_rules = _format_section(
        "写作要点：",
        [
            "- 若数据中列出多支力量或多类物资，需以分项/编号方式呈现，保证一目了然。",
            "- 对缺失信息直接写“待补充”，不得使用模糊措辞，例如“预计”“大约”“可能”。",
            "- 所有建议与请求必须基于给定数据；如需推演，请声明依据，例如“依据现有设备缺口”。",
            "- 如数据中包含技术细节（如无人机型号、桥梁名称），需精准嵌入对应段落，不得遗漏。",
        ],
    )

    return "\n".join(part for part in (header, template, guidance, writing_rules) if part)

