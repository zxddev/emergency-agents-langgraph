# Neo4j 知识图谱初始化指南

## 1. 目标
将必备的救援力量、装备、事件样本导入 Neo4j，以便救援任务生成流程能够查询资源并完成匹配。默认连接信息：

- Browser: http://192.168.20.100:7474
- Bolt URI: bolt://192.168.20.100:7687
- 用户名：`neo4j`
- 密码：`neo4jzmkj123456`

## 2. 环境准备
建议在项目根目录执行以下脚本，自动导入基础数据：

```bash
PYTHONPATH=src .venv/bin/python scripts/kg_bootstrap.py
```

运行前确认：
1. `.venv` 虚拟环境已安装依赖 (`pip install neo4j` 等)。
2. `config/dev.env` 中的 `NEO4J_URI/USER/PASSWORD` 已更新为上述值。

## 3. 脚本内容（`scripts/kg_bootstrap.py`）
脚本中示例数据包括：
- **救援力量节点** (`RescueTeam`)：消防、应急、医疗等单位，包含类型、人数、装备。
- **装备节点** (`Equipment`)：生命探测仪、破拆器材等。
- **事件节点** (`DisasterEvent`)：历史地震案例，用于 RAG/案例匹配。
- **关系**：
  - `(:RescueTeam)-[:OWNS]->(:Equipment)`
  - `(:RescueTeam)-[:COVER_REGION]->(:Region)`
  - `(:DisasterEvent)-[:REQUIRES]->(:Equipment)`

示例 Python 脚本（可根据实际情况扩展）：

```python
from neo4j import GraphDatabase

URI = "bolt://192.168.20.100:7687"
USER = "neo4j"
PASSWORD = "neo4jzmkj123456"

TEAMS = [
    {
        "id": "team_fire_001",
        "name": "四川省消防救援总队",
        "type": "fire_rescue",
        "headcount": 120,
        "equipment": ["life_detector", "rescue_rope", "hydraulic_cutter"],
        "region": "四川省阿坝州",
        "lng": 103.83,
        "lat": 31.68,
    },
    {
        "id": "team_medical_001",
        "name": "成都第六医院应急医疗队",
        "type": "medical",
        "headcount": 60,
        "equipment": ["field_hospital", "trauma_kit"],
        "region": "四川省成都市",
        "lng": 104.07,
        "lat": 30.67,
    },
]

EQUIPMENTS = [
    {"id": "life_detector", "name": "生命探测仪", "category": "search"},
    {"id": "rescue_rope", "name": "救援绳索", "category": "rescue"},
    {"id": "hydraulic_cutter", "name": "液压破拆器材", "category": "rescue"},
    {"id": "field_hospital", "name": "野战医院装备", "category": "medical"},
    {"id": "trauma_kit", "name": "创伤急救包", "category": "medical"},
]

DISASTERS = [
    {"id": "case_wenchuan_2008", "name": "汶川地震案例", "type": "earthquake", "severity": "severe"},
]

def main():
    driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
    with driver.session() as session:
        session.run("MATCH (n) DETACH DELETE n")

        for equip in EQUIPMENTS:
            session.run(
                """
                MERGE (e:Equipment {id: $id})
                SET e.name = $name, e.category = $category
                """,
                equip,
            )

        for team in TEAMS:
            session.run(
                """
                MERGE (t:RescueTeam {id: $id})
                SET t.name = $name,
                    t.type = $type,
                    t.headcount = $headcount,
                    t.region = $region,
                    t.lng = $lng,
                    t.lat = $lat
                """,
                team,
            )
            for equip_id in team["equipment"]:
                session.run(
                    """
                    MATCH (t:RescueTeam {id: $team_id})
                    MATCH (e:Equipment {id: $equip_id})
                    MERGE (t)-[:OWNS]->(e)
                    """,
                    {"team_id": team["id"], "equip_id": equip_id},
                )

        for disaster in DISASTERS:
            session.run(
                """
                MERGE (d:DisasterEvent {id: $id})
                SET d.name = $name, d.type = $type, d.severity = $severity
                """,
                disaster,
            )
        session.run(
            """
            MATCH (d:DisasterEvent {id: 'case_wenchuan_2008'})
            MATCH (e:Equipment {id: 'life_detector'})
            MERGE (d)-[:REQUIRES]->(e)
            """
        )

    driver.close()

if __name__ == "__main__":
    main()
```

> ⚠️ *删除所有节点*：脚本开头的 `MATCH (n) DETACH DELETE n` 会清空现有图谱，若已存在正式数据，请先备份或移除该语句。

## 4. 直接在 Neo4j Desktop / Browser 执行
若无需脚本，可在 Browser 里分步执行 Cypher：

```cypher
// 清空
MATCH (n) DETACH DELETE n;

// 装备
UNWIND [
  {id:'life_detector', name:'生命探测仪', category:'search'},
  {id:'rescue_rope', name:'救援绳索', category:'rescue'}
] AS equip
MERGE (e:Equipment {id:equip.id})
SET e.name = equip.name, e.category = equip.category;

// 救援队伍
MERGE (t:RescueTeam {id:'team_fire_001'})
SET t.name='四川省消防救援总队',
    t.type='fire_rescue',
    t.headcount=120,
    t.region='四川省阿坝州',
    t.lng=103.83,
    t.lat=31.68;

MATCH (t:RescueTeam {id:'team_fire_001'}), (e:Equipment {id:'life_detector'})
MERGE (t)-[:OWNS]->(e);
```

## 5. 验证
- 在 Neo4j Browser 中执行 `MATCH (n) RETURN labels(n), count(*)` 确认节点数量。
- 项目启动后，再次调用 `/intent/process`，确保不再出现“缺少知识图谱支撑”。
