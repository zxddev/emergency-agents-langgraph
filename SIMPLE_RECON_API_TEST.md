# 简化侦察方案API测试指南

## 新API端点

**地址**: `POST http://localhost:8008/ai/recon/simple-plan`

**特点**:
- ✅ 直接提供设备和目标，AI智能生成任务
- ✅ 无天气评估
- ✅ 无增援分析
- ✅ 极简流程，快速响应

---

## 完整测试示例

### 1. 基础洪灾场景

```bash
curl -X POST http://localhost:8008/ai/recon/simple-plan \
  -H "Content-Type: application/json" \
  -d '{
  "disaster_type": "flood",
  "severity": "critical",
  "epicenter": {
    "lon": 120.5,
    "lat": 30.2
  },
  "command_center": {
    "lon": 120.48,
    "lat": 30.18
  },
  "devices": [
    {
      "id": "uav-001",
      "name": "扫图无人机",
      "device_type": "drone",
      "env_type": "air",
      "capabilities": ["mapping", "aerial_recon", "thermal_imaging"]
    },
    {
      "id": "dog-001",
      "name": "搜救机器狗",
      "device_type": "robot_dog",
      "env_type": "land",
      "capabilities": ["search_rescue", "terrain_traversal"]
    },
    {
      "id": "ship-001",
      "name": "水域侦察船",
      "device_type": "usv",
      "env_type": "sea",
      "capabilities": ["water_recon", "sonar"]
    }
  ],
  "targets": [
    {
      "id": 101,
      "name": "受灾村庄A",
      "target_type": "residential",
      "hazard_level": "high",
      "priority": 0.95,
      "lon": 120.52,
      "lat": 30.25
    },
    {
      "id": 102,
      "name": "化工厂区域",
      "target_type": "industrial",
      "hazard_level": "critical",
      "priority": 0.98,
      "lon": 120.55,
      "lat": 30.28
    },
    {
      "id": 103,
      "name": "桥梁断裂点",
      "target_type": "infrastructure",
      "hazard_level": "medium",
      "priority": 0.75,
      "lon": 120.48,
      "lat": 30.22
    }
  ]
}'
```

### 2. 地震场景（多设备）

```bash
curl -X POST http://localhost:8008/ai/recon/simple-plan \
  -H "Content-Type: application/json" \
  -d '{
  "disaster_type": "earthquake",
  "severity": "high",
  "epicenter": {
    "lon": 118.5,
    "lat": 32.8
  },
  "command_center": {
    "lon": 118.48,
    "lat": 32.78
  },
  "devices": [
    {
      "id": "uav-002",
      "name": "高清航拍无人机",
      "device_type": "drone",
      "env_type": "air",
      "capabilities": ["4k_video", "mapping"]
    },
    {
      "id": "uav-003",
      "name": "热成像无人机",
      "device_type": "drone",
      "env_type": "air",
      "capabilities": ["thermal_imaging", "night_vision"]
    },
    {
      "id": "dog-002",
      "name": "废墟搜救犬",
      "device_type": "robot_dog",
      "env_type": "land",
      "capabilities": ["search_rescue", "gas_detection"]
    }
  ],
  "targets": [
    {
      "id": 201,
      "name": "倒塌居民楼",
      "target_type": "residential",
      "hazard_level": "critical",
      "priority": 0.99,
      "lon": 118.52,
      "lat": 32.82
    },
    {
      "id": 202,
      "name": "医院建筑",
      "target_type": "hospital",
      "hazard_level": "high",
      "priority": 0.95,
      "lon": 118.54,
      "lat": 32.84
    }
  ]
}'
```

### 3. 化工泄露场景（单设备测试）

```bash
curl -X POST http://localhost:8008/ai/recon/simple-plan \
  -H "Content-Type: application/json" \
  -d '{
  "disaster_type": "chemical_leak",
  "severity": "critical",
  "epicenter": {
    "lon": 121.2,
    "lat": 31.5
  },
  "command_center": {
    "lon": 121.18,
    "lat": 31.48
  },
  "devices": [
    {
      "id": "dog-003",
      "name": "防化机器狗",
      "device_type": "robot_dog",
      "env_type": "land",
      "capabilities": ["hazmat_detection", "gas_detection", "thermal_imaging"]
    }
  ],
  "targets": [
    {
      "id": 301,
      "name": "化工罐区",
      "target_type": "industrial",
      "hazard_level": "critical",
      "priority": 1.0,
      "lon": 121.22,
      "lat": 31.52
    }
  ]
}'
```

---

## 响应格式示例

```json
{
  "trace_id": "3a6254e1-fdc9-451a-af92-17446dc38129",
  "success": true,
  "message": "侦察方案生成成功",
  "command_center": {
    "lon": 120.48,
    "lat": 30.18
  },
  "command_center_name": "指挥中心",
  "disaster_type": "flood",
  "severity": "critical",
  "epicenter": {
    "lon": 120.5,
    "lat": 30.2
  },
  "air_recon_section": {
    "section_name": "空中侦察",
    "tasks": [
      {
        "task_number": "1",
        "task_type": "扫图建模",
        "device_id": "uav-001",
        "device_name": "扫图无人机",
        "device_selection_reason": "设备具备mapping和aerial_recon能力，适合进行大范围扫图",
        "target_ids": [101, 102, 103],
        "target_names": ["受灾村庄A", "化工厂区域", "桥梁断裂点"],
        "reconnaissance_detail": "飞行路线：指挥中心 → 受灾村庄A → 化工厂区域 → 桥梁断裂点，采集4K航拍数据和热成像图",
        "result_reporting": "实时回传航拍视频、3D建模数据、热成像数据",
        "start_time": "2025-01-03 18:30:00",
        "end_time": "2025-01-03 19:30:00",
        "estimated_duration_minutes": 60,
        "route_distance_km": 12.5
      }
    ]
  },
  "ground_recon_section": {
    "section_name": "地面侦察",
    "tasks": [
      {
        "task_number": "1",
        "task_type": "地面搜救",
        "device_id": "dog-001",
        "device_name": "搜救机器狗",
        "device_selection_reason": "设备具备search_rescue和terrain_traversal能力，适合废墟搜救",
        "target_ids": [101],
        "target_names": ["受灾村庄A"],
        "reconnaissance_detail": "进入村庄废墟，使用声呐和热成像探测生命迹象",
        "result_reporting": "回传生命体征探测结果、现场照片、GPS定位",
        "start_time": "2025-01-03 19:30:00",
        "end_time": "2025-01-03 21:00:00",
        "estimated_duration_minutes": 90,
        "route_distance_km": 4.2
      }
    ]
  },
  "water_recon_section": {
    "section_name": "水域侦察",
    "tasks": [
      {
        "task_number": "1",
        "task_type": "水域探测",
        "device_id": "ship-001",
        "device_name": "水域侦察船",
        "device_selection_reason": "设备具备water_recon和sonar能力，适合淹没区域探测",
        "target_ids": [103],
        "target_names": ["桥梁断裂点"],
        "reconnaissance_detail": "使用声呐探测桥梁水下结构损坏情况，采集水深数据",
        "result_reporting": "回传声呐数据、水深图、水下结构照片",
        "start_time": "2025-01-03 21:00:00",
        "end_time": "2025-01-03 22:30:00",
        "estimated_duration_minutes": 90,
        "route_distance_km": 3.8
      }
    ]
  },
  "data_integration_desc": "将空中扫图、地面搜救、水域探测数据整合，形成立体态势图，为救援决策提供全面支持",
  "earliest_start_time": "2025-01-03 18:30:00",
  "latest_end_time": "2025-01-03 22:30:00",
  "total_estimated_hours": 4.0
}
```

---

## 错误处理

### 1. 设备列表为空
```json
{
  "detail": "输入验证失败: 设备列表为空"
}
```

### 2. 目标列表为空
```json
{
  "detail": "输入验证失败: 目标列表为空"
}
```

### 3. LLM调用失败（会自动降级到简单规则分配）
```json
{
  "success": true,
  "message": "侦察方案生成成功",
  "data_integration_desc": "简单规则分配，LLM失败降级方案",
  ...
}
```

---

## 与旧API的对比

| 特性 | `/ai/recon/batch-weather-plan` (旧) | `/ai/recon/simple-plan` (新) |
|------|-----------------------------------|----------------------------|
| **流程** | 数据库查设备 → 天气评估 → 增援分析 → LLM生成 | 直接LLM生成 |
| **输入** | 灾情+区域+半径 | 灾情+设备+目标 |
| **天气评估** | ✅ 有 | ❌ 无 |
| **增援分析** | ✅ 有 | ❌ 无 |
| **响应速度** | 慢（多步骤） | 快（单步骤） |
| **适用场景** | 完整决策流程 | 快速任务分配 |

---

## 测试检查清单

- [ ] 基础洪灾场景（3设备3目标）
- [ ] 地震场景（3设备2目标）
- [ ] 化工泄露场景（1设备1目标）
- [ ] 空设备列表（预期400错误）
- [ ] 空目标列表（预期400错误）
- [ ] LLM降级策略（关闭LLM测试）
- [ ] 响应时间 < 10秒
- [ ] 日志完整性检查

---

## 快速启动服务

```bash
cd /home/msq/gitCode/new_1/emergency-agents-langgraph
./scripts/dev-run.sh

# 查看日志
tail -f temp/server.log

# 健康检查
curl http://localhost:8008/healthz
```

---

**创建时间**: 2025-01-03
**API版本**: v1.0
**端点**: `/ai/recon/simple-plan`
