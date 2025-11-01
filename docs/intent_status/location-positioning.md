# 意图：location-positioning

## 标准槽位
- `target_type`（event/team/poi）
- `event_id` / `event_code`（针对事件）
- `team_id` / `team_name`（针对队伍）
- `poi_name`（针对 POI）

## 当前实现
- Handler 位于 `src/emergency_agents/intent/handlers/location_positioning.py`：
  - 事件/队伍：查询 PostgreSQL 坐标。
  - POI：数据库未命中时调用高德地理编码。
  - 返回 `locate_*` payload 并记录 Java TODO 日志。

## 待完成闭环
1. **前端联动**：调用 `emergency-web-api` 或直接推送 WebSocket，让前端地图跳转到目标位置。
2. **经纬度验证**：增加坐标有效性检查、空值报错信息。
3. **日志追踪**：给每次定位生成 trace_id，方便排查。
4. **POI 缓存**：对高德结果做缓存或落库，减少重复调用。

## 依赖与注意事项
- 需要配置 `AmapClient` 的 API key、超时、缓存策略。
- 注意处理多个队伍同名的模糊匹配，必要时返回候选列表。
