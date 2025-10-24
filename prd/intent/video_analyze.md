# PRD: video_analyze（视频/报告驱动的目标分析）

## 1. 背景与目标
- 演示期无真实视频链，支持两种入口：
  1) 报告模式（默认）：专家口述/文本“在X处发现Y”，生成候选标注（PENDING）；
  2) 视频模式（可选）：若接入WebRTC，按通道/模态/目标生成候选标注（PENDING）。

## 2. 用户故事
- 报告：“在水磨镇坐标31.68,103.85发现被困群众10人。”
- （可选）视频：“查看无人机热像，识别是否有烟雾。”

## 3. 意图定义
- intent_type = `video_analyze`
- 演示默认走报告模式，无需实时视频。

## 4. 槽位Schema（JSON）
```json
{
  "type": "object",
  "properties": {
    "mode": {"enum": ["report", "webrtc"], "default": "report"},
    "location_text": {"type": "string"},
    "lat": {"type": "number"},
    "lng": {"type": "number"},
    "target": {"enum": ["person", "smoke", "fire", "water", "debris", "bridge_damage", "vehicle_block"]},
    "count": {"type": "number"},
    "channel": {"enum": ["uav", "robotdog_cam"]},
    "modality": {"enum": ["EO", "IR", "Zoom", "GAS"]}
  },
  "required": ["target"]
}
```

## 5. 解析与读回
- report：优先抽取经纬度/地名/数量→生成候选标注（PENDING）。
- webrtc（可选）：抽取通道/模态/目标→候选标注（PENDING）。
- 读回：“已生成‘被困人员’候选标注1处（PENDING），请签收或驳回。”

## 6. 流程与接口
- 路由：intent→video_analyze→候选标注（PENDING）→等待 `annotation_sign`。
- Java：`POST /annotations`（PENDING）【TODO】。

## 7. 兜底
- 缺坐标：读回“是否使用地名X解析到(…, …)？”；
- 无目标：拒绝受理并提示补充。

## 8. 验收
- few‑shot≥20；报告抽槽准确率≥0.9；签收闭环可演示。
