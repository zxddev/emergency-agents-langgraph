# 地图图层规范（GeoJSON / WGS84）

## 通用
- 坐标系：WGS84；
- 时间：ISO8601；
- 上屏时延：标注签收或报告后 ≤ 2s（演示）。

## 图层与字段
1) annotations（标注）
- Feature: geometry=Point/LineString/Polygon；
- properties: {id,label,status:PENDING|SIGNED|REJECTED,confidence,evidence[],updated_at}

2) uav_tracks（轨迹）
- geometry=LineString；properties: {id,alt_m,steps,generated_at}

3) routes（路线）
- geometry=LineString；properties: {id,policy:best|fastest|safest,cost:{time,risk,energy},segments[]}

4) safe_points（安全点）
- geometry=Point；properties: {id,score,reason[]}

5) events（事件）
- geometry=Point|Polygon；properties: {id,type,severity,title,description,parent_event_id,status}

6) tasks（任务）
- geometry=Point|LineString；properties: {id,title,plan_id,unit_id,status,window}

## 验收
- GeoJSON校验通过；字段完整；渲染一致。
