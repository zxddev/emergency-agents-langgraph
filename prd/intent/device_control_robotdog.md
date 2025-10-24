# PRD: device_control_robotdog（机器狗控制）

## 1. 背景与目标
- 通过语音/文本控制机器狗：移动/转向/抬头/到点/急停。演示期仅保留接口TODO与确认规范，不做真实控制。

## 2. 用户故事（例）
- “前进三米，向右转九十度。”
- “抬头十五度。”
- “到坐标31.68,103.85。”
- “急停！”

## 3. 意图定义
- intent_type = `device_control_robotdog`

## 4. 槽位Schema（JSON）
```json
{
  "type": "object",
  "properties": {
    "action": {"enum": ["move", "turn", "head", "goto", "stop", "e_stop"]},
    "distance_m": {"type": "number", "minimum": 0.1, "maximum": 20},
    "angle_deg": {"type": "number", "minimum": -180, "maximum": 180},
    "lat": {"type": "number"},
    "lng": {"type": "number"},
    "speed": {"type": "number", "minimum": 0.1, "maximum": 2.0}
  },
  "required": ["action"]
}
```

## 5. 解析与读回（高风险统一双确认）
- few‑shot抽槽；
- 若 action ∈ {move, goto, turn} → 读回“将执行机器狗动作：{action} 参数={slots}，请确认”；
- e_stop/stop 立即接受，读回“已下发急停/停止”。

## 6. 流程与接口
- Java（TODO）：`POST /control/robotdog/command` {action, params}

## 7. 错误与兜底
- 参数越界：读回“距离/角度超限，请重试”；
- 坐标缺失：追问“是否前往地名X或输入经纬度？”

## 8. 验收KPI
- few‑shot≥20；控制类F1≥0.95；确认命中率100%。
