# 意图：recon_minimal

## 标准槽位
- `lng`
- `lat`
- `alt_m`（默认80）
- `steps`（默认20）

## 当前实现
- 处理逻辑在 `src/emergency_agents/intent/router.py`：生成 UAV 轨迹（GeoJSON），追加到 `uav_tracks`，并记录 timeline 事件。

## 待完成闭环
1. **轨迹下发**：把生成的轨迹传给无人机控制系统或仿真模块。
2. **可视化同步**：确保前端地图展示新轨迹，并支持删除/调整。
3. **轨迹参数校验**：防止非法高度/步数导致轨迹异常。

## 依赖与注意事项
- 使用 `build_track_feature` 构造轨迹，依赖初始 `fleet_position`。
- 若引入真实控制，应增加 interrupt 二次确认。
