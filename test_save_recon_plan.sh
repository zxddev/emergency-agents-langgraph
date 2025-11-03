#!/bin/bash
# 侦察方案生成与保存测试脚本

set -e

echo "========================================="
echo "侦察方案生成与保存测试"
echo "========================================="
echo ""

# 配置
API_BASE="http://localhost:8008"
INCIDENT_ID="550e8400-e29b-41d4-a716-446655440000"
CREATED_BY="operator_test_001"

# 临时文件
PLAN_FILE="temp/test_plan_$(date +%s).json"
SAVE_RESULT="temp/test_save_result_$(date +%s).json"

# 确保temp目录存在
mkdir -p temp

echo "步骤1: 生成侦察方案..."
echo "-------------------------------------------"
curl -s -X POST "$API_BASE/ai/recon/batch-weather-plan" \
  -H "Content-Type: application/json" \
  -d '{
    "disaster_type": "flood",
    "epicenter": {"lon": 103.8, "lat": 31.66},
    "severity": "critical"
  }' > "$PLAN_FILE"

if [ ! -s "$PLAN_FILE" ]; then
    echo "❌ 生成侦察方案失败"
    exit 1
fi

echo "✅ 侦察方案生成成功"
echo "方案摘要:"
jq -r '{
  success: .success,
  total_targets: .total_targets,
  suitable_devices: .suitable_devices_count,
  batches_count: (.batches | length),
  has_air_section: (.detailed_plan.air_recon_section != null),
  has_ground_section: (.detailed_plan.ground_recon_section != null),
  has_water_section: (.detailed_plan.water_recon_section != null)
}' "$PLAN_FILE"
echo ""

echo "步骤2: 保存侦察方案到草稿表..."
echo "-------------------------------------------"
PLAN_DATA=$(cat "$PLAN_FILE")

curl -s -X POST "$API_BASE/ai/recon/save-plan" \
  -H "Content-Type: application/json" \
  -d "{
    \"incident_id\": \"$INCIDENT_ID\",
    \"plan_data\": $PLAN_DATA,
    \"created_by\": \"$CREATED_BY\"
  }" > "$SAVE_RESULT"

if [ ! -s "$SAVE_RESULT" ]; then
    echo "❌ 保存侦察方案失败"
    exit 1
fi

echo "✅ 侦察方案保存成功"
echo "保存结果:"
cat "$SAVE_RESULT" | python3 -m json.tool
echo ""

# 提取snapshot_id
SNAPSHOT_ID=$(jq -r '.snapshot_id' "$SAVE_RESULT")

if [ "$SNAPSHOT_ID" = "null" ] || [ -z "$SNAPSHOT_ID" ]; then
    echo "❌ 未获取到snapshot_id"
    exit 1
fi

echo "步骤3: 查询已保存的方案..."
echo "-------------------------------------------"
echo "查询事件的所有方案:"
curl -s "$API_BASE/ai/recon/list-plans/$INCIDENT_ID?limit=5" \
  | jq -r '.[] | {
      snapshot_id: .snapshot_id,
      created_at: .created_at,
      created_by: .created_by,
      targets: .payload.total_targets,
      devices: .payload.suitable_devices_count
    }'
echo ""

echo "步骤4: 获取特定方案详情..."
echo "-------------------------------------------"
echo "查询快照ID: $SNAPSHOT_ID"
curl -s "$API_BASE/ai/recon/get-plan/$SNAPSHOT_ID" \
  | jq '{
      snapshot_id: .snapshot_id,
      incident_id: .incident_id,
      created_at: .created_at,
      created_by: .created_by,
      plan_summary: {
        success: .payload.success,
        total_targets: .payload.total_targets,
        batches_count: (.payload.batches | length),
        air_tasks: (.payload.detailed_plan.air_recon_section.tasks | length),
        ground_tasks: (.payload.detailed_plan.ground_recon_section.tasks | length),
        water_tasks: (.payload.detailed_plan.water_recon_section.tasks | length),
        earliest_start: .payload.detailed_plan.earliest_start_time,
        latest_end: .payload.detailed_plan.latest_end_time,
        total_hours: .payload.detailed_plan.total_estimated_hours
      }
    }'
echo ""

echo "步骤5: 验证数据库存储..."
echo "-------------------------------------------"
PGPASSWORD=postgres123 psql -h 8.147.130.215 -p 19532 -U postgres -d emergency_agent \
  -c "SELECT
        snapshot_id::text,
        incident_id::text,
        snapshot_type,
        created_by,
        created_at,
        jsonb_pretty(payload -> 'detailed_plan' -> 'disaster_info') as disaster_info
      FROM operational.incident_snapshots
      WHERE snapshot_id = '$SNAPSHOT_ID'::uuid;"

echo ""
echo "========================================="
echo "✅ 测试完成！"
echo "========================================="
echo ""
echo "保存的快照ID: $SNAPSHOT_ID"
echo "关联的事件ID: $INCIDENT_ID"
echo "创建者: $CREATED_BY"
echo ""
echo "清理临时文件..."
# rm -f "$PLAN_FILE" "$SAVE_RESULT"
echo "临时文件保留在 temp/ 目录，手动清理"
echo ""
