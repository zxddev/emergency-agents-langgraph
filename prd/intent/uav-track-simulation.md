# UAV 轨迹模拟规范（非飞控）

## 目标
- 在无真实飞控情况下，为侦察/观察生成可视化轨迹（LineString）上屏。

## 规则
- 起点：车队当前位置（或最近一次记录点）。
- 终点：
  - point：目标Point；
  - route：LineString中点；
  - area：Polygon重心。
- 插值：默认steps=20等距插值；
- 高度：alt_m 默认80（可被意图覆盖）。
- 时间轴：timeline 写入 {event:"uav_track_generated", track_id, alt_m, steps, generated_at}。

## 输出（示例）
```json
{
  "type": "LineString",
  "coordinates": [[103.80,31.66],[...],[103.85,31.68]],
  "properties": {"alt_m": 80, "steps": 20}
}
```

## 验收
- 轨迹渲染正确；timeline事件齐全；参数可覆盖。
