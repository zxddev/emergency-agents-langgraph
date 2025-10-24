# Java API 契约（TODO · 占位）

> 本文档仅定义接口签名与请求/响应示例，当前阶段不实现调用。

## 事件
- POST /events
```json
{
  "event_type": "landslide",
  "title": "XX乡滑坡",
  "lat": 31.70, "lng": 103.90,
  "severity": "HIGH", "description": "...",
  "parent_event_id": null
}
```

## 标注
- POST /annotations（PENDING）
- POST /annotations/{id}/sign

## 方案与任务
- POST /plans
- POST /tasks/bulk

## 路线与安全点
- GET /routes?lat=...&lng=...&policy=best|fastest|safest
- GET /safe-points?near=lat,lng

## 设备状态与控制
- GET /devices/status?type=uav|robotdog&id=...&metric=...
- POST /control/robotdog/command {action, params}

## RFA 与证据
- POST /rfa
- POST /evidence/bookmark
- GET /evidence/playback?target_type=...&target_id=...&duration_sec=...
