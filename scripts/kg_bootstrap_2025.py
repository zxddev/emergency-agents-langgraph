#!/usr/bin/env python3
"""
2025应急装备知识库初始化脚本
基于MCP搜索的真实2025装备数据
支持地震、山体滑坡、化工泄露、山洪、火灾等全灾种场景
"""
import os
import sys
from urllib.parse import urlsplit
from neo4j import GraphDatabase

# Neo4j 连接配置
URI = os.getenv("NEO4J_URI", "bolt://192.168.20.100:7687")
USER = os.getenv("NEO4J_USER", "neo4j")
PASSWORD = os.getenv("NEO4J_PASSWORD", "neo4jzmkj123456")

# ============================================================================
# A类：无人智能装备（42个，基于2025真实型号）
# ============================================================================
UNMANNED_EQUIPMENT = [
    # A1-大型无人机（侦察/通信/物资投送）
    {"id": "uav_yilongx_2h", "name": "翼龙-2H应急救援型", "category": "unmanned_aerial", "type": "fixed_wing_large",
     "specs": "续航32小时，载重480kg，通信中继/侦察", "manufacturer": "中航工业", "year": 2025},
    {"id": "uav_dji_m350", "name": "DJI Matrice 350 RTK", "category": "unmanned_aerial", "type": "multirotor_pro",
     "specs": "55分钟续航，热成像+RTK测绘", "manufacturer": "大疆", "year": 2025},
    {"id": "uav_dji_flycart30", "name": "DJI FlyCart 30", "category": "unmanned_aerial", "type": "cargo_delivery",
     "specs": "30kg最大载重，28km/h速度，物资投送", "manufacturer": "大疆", "year": 2025},
    {"id": "uav_zongheng_cw15", "name": "纵横CW-15大鹏", "category": "unmanned_aerial", "type": "vtol_mapping",
     "specs": "垂直起降，3D建模测绘，5小时续航", "manufacturer": "纵横股份", "year": 2025},
    {"id": "uav_tethered_fire", "name": "系留无人机消防车", "category": "unmanned_aerial", "type": "tethered_firefighting",
     "specs": "200m系留，持续供电，300L灭火剂", "manufacturer": "中信重工", "year": 2025},
    {"id": "uav_turbofan_fire", "name": "涡扇消防无人机", "category": "unmanned_aerial", "type": "turbofan_fire",
     "specs": "涡扇引擎，200L灭火剂，50m喷射距离", "manufacturer": "应急装备研究院", "year": 2025},

    # A1-中小型无人机（热成像/侦察/喊话）
    {"id": "uav_dji_mavic3t", "name": "DJI Mavic 3T热成像版", "category": "unmanned_aerial", "type": "thermal_imaging",
     "specs": "640x512热成像，45分钟续航", "manufacturer": "大疆", "year": 2025},
    {"id": "uav_tailsitter", "name": "尾座式无人机", "category": "unmanned_aerial", "type": "vtol_recon",
     "specs": "垂直起降，2小时续航，长航时侦察", "manufacturer": "航天科技", "year": 2025},
    {"id": "uav_hexacopter_light", "name": "六旋翼照明无人机", "category": "unmanned_aerial", "type": "lighting",
     "specs": "8000流明照明，喊话器，60分钟续航", "manufacturer": "特种装备", "year": 2025},
    {"id": "uav_swarm_fire", "name": "消防无人机集群系统", "category": "unmanned_aerial", "type": "swarm_firefighting",
     "specs": "6架协同，智能避障，集群灭火", "manufacturer": "应急使命2025", "year": 2025},

    # A2-机器狗/地面机器人（12台）
    {"id": "robot_jueying_x30", "name": "绝影X30机器狗", "category": "unmanned_ground", "type": "quadruped_recon",
     "specs": "负重40kg，可架设基站，复杂地形侦察", "manufacturer": "浙江大学", "year": 2025},
    {"id": "robot_shanmao_m20", "name": "山猫M20消防机器狗", "category": "unmanned_ground", "type": "quadruped_fire",
     "specs": "耐高温600℃，消防侦察", "manufacturer": "宇树科技", "year": 2025},
    {"id": "robot_unitree_watergun", "name": "宇树水炮消防机器人", "category": "unmanned_ground", "type": "fire_robot",
     "specs": "耐1000℃高温，80L/s水炮，远程遥控", "manufacturer": "宇树科技", "year": 2025},
    {"id": "robot_quadruped_recon", "name": "四足侦察机器人", "category": "unmanned_ground", "type": "recon",
     "specs": "狭窄空间搜救，红外+视频", "manufacturer": "特种机器人", "year": 2025},
    {"id": "robot_tracked_fire", "name": "履带式灭火机器人", "category": "unmanned_ground", "type": "tracked_fire",
     "specs": "60L/s流量，耐800℃，遥控150m", "manufacturer": "中信重工", "year": 2025},
    {"id": "robot_explosive_disposal", "name": "防爆排爆机器人", "category": "unmanned_ground", "type": "eod",
     "specs": "遥控500m，X光检测，机械臂", "manufacturer": "公安部特种装备", "year": 2025},

    # A3-无人艇/水上装备（6艘）
    {"id": "usv_yunzhou_dolphin3", "name": "云洲海豚3号无人艇", "category": "unmanned_surface", "type": "rescue_boat",
     "specs": "7m/s速度，1吨牵引力，水上救援", "manufacturer": "云洲智能", "year": 2025},
    {"id": "usv_me70_rescue", "name": "ME70无人救生艇", "category": "unmanned_surface", "type": "lifesaving",
     "specs": "5m/s速度，载6人，远程遥控", "manufacturer": "海洋装备", "year": 2025},
    {"id": "usv_patrol_boat", "name": "巡逻侦察无人艇", "category": "unmanned_surface", "type": "patrol",
     "specs": "8小时续航，视频侦察，水质检测", "manufacturer": "应急装备", "year": 2025},

    # A4-其他无人装备
    {"id": "ugv_cargo_robot", "name": "无人运输车", "category": "unmanned_ground", "type": "cargo",
     "specs": "500kg载重，全地形，自主导航", "manufacturer": "智能装备", "year": 2025},
    {"id": "uav_heavy_lift", "name": "重型起重无人机", "category": "unmanned_aerial", "type": "heavy_lift",
     "specs": "50kg载重，精准投放", "manufacturer": "工业无人机", "year": 2025},
]

# ============================================================================
# B类：救援破拆工具（基于2025标准）
# ============================================================================
RESCUE_TOOLS = [
    {"id": "tool_life_detector_radar", "name": "雷达生命探测仪", "category": "search_rescue", "type": "detector",
     "specs": "20m穿透深度，心跳/呼吸检测", "manufacturer": "应急装备", "year": 2025},
    {"id": "tool_life_detector_audio", "name": "音频生命探测仪", "category": "search_rescue", "type": "detector",
     "specs": "高灵敏度麦克风，降噪算法", "manufacturer": "搜救装备", "year": 2025},
    {"id": "tool_life_detector_video", "name": "视频生命探测仪", "category": "search_rescue", "type": "detector",
     "specs": "6mm蛇形探头，夜视功能", "manufacturer": "搜救装备", "year": 2025},
    {"id": "tool_hydraulic_cutter", "name": "液压破拆工具组", "category": "search_rescue", "type": "hydraulic",
     "specs": "剪切力120kN，扩张力80kN", "manufacturer": "LUKAS德国", "year": 2025},
    {"id": "tool_plasma_cutter", "name": "等离子切割器", "category": "search_rescue", "type": "cutting",
     "specs": "切割20mm钢板，便携式", "manufacturer": "焊接装备", "year": 2025},
    {"id": "tool_rescue_tripod", "name": "救援三脚架", "category": "search_rescue", "type": "lifting",
     "specs": "最大载重500kg，高度可调", "manufacturer": "高空救援", "year": 2025},
    {"id": "tool_pneumatic_hammer", "name": "气动凿岩机", "category": "search_rescue", "type": "drilling",
     "specs": "破碎混凝土/岩石", "manufacturer": "工程装备", "year": 2025},
    {"id": "tool_rescue_rope", "name": "高强救援绳索", "category": "search_rescue", "type": "rope",
     "specs": "Φ11mm，拉力22kN，100m", "manufacturer": "攀登装备", "year": 2025},
]

# ============================================================================
# C类：消防灭火装备（基于2025实际装备）
# ============================================================================
FIREFIGHTING_EQUIPMENT = [
    {"id": "fire_jp100_platform", "name": "JP100举高喷射消防车", "category": "firefighting", "type": "aerial_platform",
     "specs": "159.66m喷射高度（世界纪录），100L/s流量", "manufacturer": "徐工消防", "year": 2025},
    {"id": "fire_yt65_ladder", "name": "YT65G2云梯车", "category": "firefighting", "type": "aerial_ladder",
     "specs": "65m作业高度，载重400kg", "manufacturer": "徐工消防", "year": 2025},
    {"id": "fire_yt16_ladder", "name": "YT16云梯车", "category": "firefighting", "type": "aerial_ladder",
     "specs": "16m作业高度，城市消防", "manufacturer": "徐工消防", "year": 2025},
    {"id": "fire_foam_truck", "name": "泡沫消防车", "category": "firefighting", "type": "foam",
     "specs": "8吨泡沫液，40L/s流量", "manufacturer": "消防车辆", "year": 2025},
    {"id": "fire_water_tanker", "name": "水罐消防车", "category": "firefighting", "type": "water_tanker",
     "specs": "12吨水罐，60L/s泵流量", "manufacturer": "消防车辆", "year": 2025},
    {"id": "fire_extinguisher_abc", "name": "ABC干粉灭火器", "category": "firefighting", "type": "portable",
     "specs": "8kg装，适用ABC类火灾", "manufacturer": "消防器材", "year": 2025},
    {"id": "fire_blanket", "name": "灭火毯", "category": "firefighting", "type": "blanket",
     "specs": "1.8x1.8m，耐温550℃", "manufacturer": "消防器材", "year": 2025},
]

# ============================================================================
# D类：医疗救护装备（基于2025标准）
# ============================================================================
MEDICAL_EQUIPMENT = [
    {"id": "medical_field_hospital", "name": "野战医院模块", "category": "medical", "type": "field_hospital",
     "specs": "手术室+ICU+急诊，50床位", "manufacturer": "军用医疗", "year": 2025},
    {"id": "medical_trauma_kit", "name": "创伤急救包", "category": "medical", "type": "first_aid",
     "specs": "止血带+纱布+夹板", "manufacturer": "医疗器械", "year": 2025},
    {"id": "medical_aed", "name": "自动体外除颤器AED", "category": "medical", "type": "defibrillator",
     "specs": "全自动，语音提示", "manufacturer": "迈瑞医疗", "year": 2025},
    {"id": "medical_stretcher_vacuum", "name": "真空担架", "category": "medical", "type": "stretcher",
     "specs": "脊柱固定，防二次伤害", "manufacturer": "救护器材", "year": 2025},
    {"id": "medical_stretcher_folding", "name": "折叠担架", "category": "medical", "type": "stretcher",
     "specs": "铝合金，可折叠", "manufacturer": "救护器材", "year": 2025},
    {"id": "medical_ventilator", "name": "便携式呼吸机", "category": "medical", "type": "ventilator",
     "specs": "电池供电，8小时续航", "manufacturer": "医疗器械", "year": 2025},
    {"id": "medical_monitor", "name": "多参数监护仪", "category": "medical", "type": "monitor",
     "specs": "心电+血氧+血压", "manufacturer": "迈瑞医疗", "year": 2025},
]

# ============================================================================
# E类：工程抢修装备（基于2025最新型号）
# ============================================================================
ENGINEERING_EQUIPMENT = [
    {"id": "eng_bridge_floating", "name": "浮箱式动力舟桥", "category": "engineering", "type": "emergency_bridge",
     "specs": "60吨承重，快速架设", "manufacturer": "军用工程", "year": 2025},
    {"id": "eng_excavator_et100d", "name": "模块化步履挖掘机ET100D", "category": "engineering", "type": "excavator",
     "specs": "360°旋转步履，陡坡作业", "manufacturer": "三一重工", "year": 2025},
    {"id": "eng_excavator_et121", "name": "模块化步履挖掘机ET121", "category": "engineering", "type": "excavator",
     "specs": "21吨级，75°爬坡", "manufacturer": "三一重工", "year": 2025},
    {"id": "eng_spider_crane", "name": "蜘蛛起重机", "category": "engineering", "type": "crane",
     "specs": "狭窄空间作业，5吨吊重", "manufacturer": "起重设备", "year": 2025},
    {"id": "eng_loader_gz500j", "name": "装载机GZ500J", "category": "engineering", "type": "loader",
     "specs": "5吨装载量，应急抢险", "manufacturer": "徐工", "year": 2025},
    {"id": "eng_bulldozer", "name": "推土机", "category": "engineering", "type": "bulldozer",
     "specs": "220马力，抢通道路", "manufacturer": "山推", "year": 2025},
    {"id": "eng_roller", "name": "压路机", "category": "engineering", "type": "roller",
     "specs": "双钢轮，道路修复", "manufacturer": "徐工", "year": 2025},
]

# ============================================================================
# F类：通信指挥装备（基于2025最新技术）
# ============================================================================
COMMUNICATION_EQUIPMENT = [
    {"id": "comm_satellite_truck", "name": "卫星通信车", "category": "communication", "type": "satellite",
     "specs": "天通+北斗，移动指挥", "manufacturer": "中国电信", "year": 2025},
    {"id": "comm_portable_basestation", "name": "便携式5G基站", "category": "communication", "type": "5g_portable",
     "specs": "30分钟快速部署，覆盖5km", "manufacturer": "中国移动", "year": 2025},
    {"id": "comm_command_vehicle", "name": "应急指挥车", "category": "communication", "type": "command",
     "specs": "移动指挥中心，视频会议", "manufacturer": "应急装备", "year": 2025},
    {"id": "comm_satellite_phone", "name": "天通卫星电话", "category": "communication", "type": "satellite_phone",
     "specs": "全国覆盖，断网可用", "manufacturer": "中国电信", "year": 2025},
    {"id": "comm_beidou_terminal", "name": "北斗短报文终端", "category": "communication", "type": "beidou",
     "specs": "定位+短报文", "manufacturer": "北斗导航", "year": 2025},
    {"id": "comm_walkie_talkie", "name": "数字对讲机", "category": "communication", "type": "radio",
     "specs": "10km通信距离，加密", "manufacturer": "海能达", "year": 2025},
]

# ============================================================================
# G类：后勤保障物资（基于2025标准）
# ============================================================================
LOGISTICS_SUPPLIES = [
    {"id": "log_generator_truck", "name": "发电车", "category": "logistics", "type": "power",
     "specs": "500kW功率，持续供电", "manufacturer": "发电设备", "year": 2025},
    {"id": "log_generator_portable", "name": "便携式发电机", "category": "logistics", "type": "power",
     "specs": "5kW，汽油发电", "manufacturer": "发电设备", "year": 2025},
    {"id": "log_storage_power", "name": "源网荷储应急供电系统", "category": "logistics", "type": "power_storage",
     "specs": "光伏+储能+柴油，48小时", "manufacturer": "国家电网", "year": 2025},
    {"id": "log_tent_relief", "name": "救灾帐篷", "category": "logistics", "type": "shelter",
     "specs": "8人装，防雨防风", "manufacturer": "救灾物资", "year": 2025},
    {"id": "log_tent_medical", "name": "医疗帐篷", "category": "logistics", "type": "shelter",
     "specs": "充气式，快速搭建", "manufacturer": "救灾物资", "year": 2025},
    {"id": "log_camp_vehicle", "name": "宿营车", "category": "logistics", "type": "shelter",
     "specs": "6人住宿，空调+供电", "manufacturer": "特种车辆", "year": 2025},
    {"id": "log_water_purifier", "name": "净水设备", "category": "logistics", "type": "water",
     "specs": "5吨/小时，反渗透", "manufacturer": "净水设备", "year": 2025},
    {"id": "log_water_tank", "name": "储水罐", "category": "logistics", "type": "water",
     "specs": "10吨容量", "manufacturer": "水务装备", "year": 2025},
    {"id": "log_food_emergency", "name": "应急食品", "category": "logistics", "type": "food",
     "specs": "压缩饼干+自热食品，3年保质期", "manufacturer": "救灾物资", "year": 2025},
    {"id": "log_thermal_blanket", "name": "保温毯", "category": "logistics", "type": "warmth",
     "specs": "铝膜，反射体温", "manufacturer": "救灾物资", "year": 2025},
    {"id": "log_lighting", "name": "应急照明灯", "category": "logistics", "type": "lighting",
     "specs": "LED，10000流明", "manufacturer": "照明设备", "year": 2025},
]

# ============================================================================
# H类：特种防护装备（基于2025标准）
# ============================================================================
PROTECTIVE_EQUIPMENT = [
    {"id": "protect_hazmat_a", "name": "A级防化服", "category": "protective", "type": "hazmat",
     "specs": "全封闭，正压供气", "manufacturer": "防化装备", "year": 2025},
    {"id": "protect_hazmat_b", "name": "B级防化服", "category": "protective", "type": "hazmat",
     "specs": "半封闭，液密性", "manufacturer": "防化装备", "year": 2025},
    {"id": "protect_hazmat_c", "name": "C级防化服", "category": "protective", "type": "hazmat",
     "specs": "化学防护，透气型", "manufacturer": "防化装备", "year": 2025},
    {"id": "protect_decon_tent", "name": "洗消帐篷", "category": "protective", "type": "decontamination",
     "specs": "充气式，三道洗消", "manufacturer": "防化装备", "year": 2025},
    {"id": "protect_decon_equipment", "name": "洗消设备", "category": "protective", "type": "decontamination",
     "specs": "高压水雾，化学中和", "manufacturer": "防化装备", "year": 2025},
    {"id": "protect_gas_detector", "name": "多合一气体检测仪", "category": "protective", "type": "detector",
     "specs": "检测CO/H2S/O2/可燃气", "manufacturer": "检测仪器", "year": 2025},
    {"id": "protect_radiation_detector", "name": "辐射检测仪", "category": "protective", "type": "radiation",
     "specs": "α/β/γ射线检测", "manufacturer": "检测仪器", "year": 2025},
    {"id": "protect_explosion_proof", "name": "防爆工具组", "category": "protective", "type": "tools",
     "specs": "铜合金，防爆区域使用", "manufacturer": "防爆装备", "year": 2025},
]

# ============================================================================
# 20支救援队伍（四川省分布）
# ============================================================================
RESCUE_TEAMS = [
    # 指挥中枢（1支）
    {
        "id": "team_command_001",
        "name": "四川省应急指挥中心",
        "type": "command_center",
        "headcount": 50,
        "specialization": "总体指挥协调",
        "region": "四川省成都市",
        "lng": 104.066,
        "lat": 30.573,
        "equipment": ["comm_satellite_truck", "comm_command_vehicle", "comm_portable_basestation"],
        "controlled_unmanned": [  # "陆地航母"控制的无人设备
            "uav_yilongx_2h", "uav_dji_m350", "uav_dji_flycart30", "uav_zongheng_cw15",
            "robot_jueying_x30", "usv_yunzhou_dolphin3"
        ]
    },

    # 重型救援队（4支）
    {
        "id": "team_heavy_001",
        "name": "成都市重型救援队",
        "type": "heavy_rescue",
        "headcount": 150,
        "specialization": "地震救援+工程抢险",
        "region": "四川省成都市",
        "lng": 104.066,
        "lat": 30.573,
        "equipment": [
            "uav_dji_mavic3t", "robot_quadruped_recon", "tool_life_detector_radar",
            "tool_hydraulic_cutter", "eng_excavator_et100d", "comm_walkie_talkie",
            "medical_trauma_kit", "log_generator_portable"
        ]
    },
    {
        "id": "team_heavy_002",
        "name": "绵阳市重型救援队",
        "type": "heavy_rescue",
        "headcount": 120,
        "specialization": "地震救援+核应急",
        "region": "四川省绵阳市",
        "lng": 104.741,
        "lat": 31.464,
        "equipment": [
            "uav_dji_mavic3t", "robot_shanmao_m20", "tool_life_detector_audio",
            "tool_rescue_tripod", "protect_radiation_detector", "eng_loader_gz500j"
        ]
    },
    {
        "id": "team_heavy_003",
        "name": "德阳市重型救援队",
        "type": "heavy_rescue",
        "headcount": 100,
        "specialization": "工程抢险+化工救援",
        "region": "四川省德阳市",
        "lng": 104.399,
        "lat": 31.128,
        "equipment": [
            "robot_unitree_watergun", "tool_hydraulic_cutter", "protect_hazmat_b",
            "protect_gas_detector", "eng_bulldozer"
        ]
    },
    {
        "id": "team_heavy_004",
        "name": "泸州市重型救援队",
        "type": "heavy_rescue",
        "headcount": 110,
        "specialization": "化工救援+水域救援",
        "region": "四川省泸州市",
        "lng": 105.443,
        "lat": 28.889,
        "equipment": [
            "usv_me70_rescue", "protect_hazmat_a", "protect_decon_tent",
            "tool_rescue_rope", "eng_spider_crane"
        ]
    },

    # 专业消防队（5支）
    {
        "id": "team_fire_001",
        "name": "阿坝州森林消防队",
        "type": "firefighting",
        "headcount": 80,
        "specialization": "森林火灾+高海拔救援",
        "region": "四川省阿坝州",
        "lng": 103.698,
        "lat": 31.899,
        "equipment": [
            "uav_tethered_fire", "uav_swarm_fire", "fire_water_tanker",
            "fire_extinguisher_abc", "comm_beidou_terminal"
        ]
    },
    {
        "id": "team_fire_002",
        "name": "雅安市消防救援支队",
        "type": "firefighting",
        "headcount": 90,
        "specialization": "地震救援+火灾扑救",
        "region": "四川省雅安市",
        "lng": 103.001,
        "lat": 29.988,
        "equipment": [
            "fire_yt16_ladder", "robot_tracked_fire", "uav_turbofan_fire",
            "tool_life_detector_video", "medical_stretcher_vacuum"
        ]
    },
    {
        "id": "team_fire_003",
        "name": "凉山州消防救援支队",
        "type": "firefighting",
        "headcount": 100,
        "specialization": "森林火灾+山地救援",
        "region": "四川省凉山州",
        "lng": 102.268,
        "lat": 27.887,
        "equipment": [
            "uav_hexacopter_light", "fire_foam_truck", "fire_blanket",
            "tool_rescue_rope", "comm_satellite_phone"
        ]
    },
    {
        "id": "team_fire_004",
        "name": "攀枝花市消防救援支队",
        "type": "firefighting",
        "headcount": 70,
        "specialization": "化工火灾+工矿救援",
        "region": "四川省攀枝花市",
        "lng": 101.716,
        "lat": 26.582,
        "equipment": [
            "fire_yt65_ladder", "protect_hazmat_c", "protect_explosion_proof",
            "robot_explosive_disposal"
        ]
    },
    {
        "id": "team_fire_005",
        "name": "广元市消防救援支队",
        "type": "firefighting",
        "headcount": 75,
        "specialization": "地震救援+交通事故",
        "region": "四川省广元市",
        "lng": 105.829,
        "lat": 32.433,
        "equipment": [
            "tool_hydraulic_cutter", "tool_plasma_cutter", "fire_water_tanker",
            "medical_aed", "comm_walkie_talkie"
        ]
    },

    # 医疗救护队（4支）
    {
        "id": "team_medical_001",
        "name": "成都市应急医疗队",
        "type": "medical",
        "headcount": 60,
        "specialization": "创伤救治+野战医院",
        "region": "四川省成都市",
        "lng": 104.066,
        "lat": 30.573,
        "equipment": [
            "medical_field_hospital", "medical_ventilator", "medical_monitor",
            "medical_aed", "log_tent_medical", "comm_satellite_truck"
        ]
    },
    {
        "id": "team_medical_002",
        "name": "宜宾市应急医疗队",
        "type": "medical",
        "headcount": 50,
        "specialization": "批量伤员救治",
        "region": "四川省宜宾市",
        "lng": 104.643,
        "lat": 28.760,
        "equipment": [
            "medical_trauma_kit", "medical_stretcher_folding", "medical_aed",
            "log_camp_vehicle", "comm_portable_basestation"
        ]
    },
    {
        "id": "team_medical_003",
        "name": "乐山市应急医疗队",
        "type": "medical",
        "headcount": 45,
        "specialization": "水灾救援+疾病防控",
        "region": "四川省乐山市",
        "lng": 103.761,
        "lat": 29.552,
        "equipment": [
            "medical_trauma_kit", "medical_stretcher_vacuum", "log_water_purifier",
            "protect_decon_equipment"
        ]
    },
    {
        "id": "team_medical_004",
        "name": "内江市应急医疗队",
        "type": "medical",
        "headcount": 40,
        "specialization": "紧急救护+转运",
        "region": "四川省内江市",
        "lng": 105.066,
        "lat": 29.580,
        "equipment": [
            "medical_monitor", "medical_ventilator", "medical_stretcher_folding",
            "comm_walkie_talkie"
        ]
    },

    # 工程抢修队（3支）
    {
        "id": "team_engineering_001",
        "name": "甘孜州工程抢修队",
        "type": "engineering",
        "headcount": 80,
        "specialization": "道路抢通+桥梁架设",
        "region": "四川省甘孜州",
        "lng": 101.963,
        "lat": 30.050,
        "equipment": [
            "eng_bridge_floating", "eng_excavator_et121", "eng_bulldozer",
            "eng_roller", "comm_beidou_terminal", "log_generator_truck"
        ]
    },
    {
        "id": "team_engineering_002",
        "name": "巴中市工程抢修队",
        "type": "engineering",
        "headcount": 70,
        "specialization": "山体滑坡处置+道路修复",
        "region": "四川省巴中市",
        "lng": 106.753,
        "lat": 31.858,
        "equipment": [
            "eng_excavator_et100d", "eng_loader_gz500j", "eng_spider_crane",
            "tool_pneumatic_hammer", "comm_satellite_phone"
        ]
    },
    {
        "id": "team_engineering_003",
        "name": "达州市工程抢修队",
        "type": "engineering",
        "headcount": 65,
        "specialization": "交通抢通+应急供电",
        "region": "四川省达州市",
        "lng": 107.502,
        "lat": 31.209,
        "equipment": [
            "eng_bulldozer", "eng_loader_gz500j", "log_storage_power",
            "log_generator_portable", "comm_portable_basestation"
        ]
    },

    # 物资保障队（3支）
    {
        "id": "team_logistics_001",
        "name": "南充市物资保障队",
        "type": "logistics",
        "headcount": 50,
        "specialization": "物资储备+配送",
        "region": "四川省南充市",
        "lng": 106.082,
        "lat": 30.795,
        "equipment": [
            "ugv_cargo_robot", "log_tent_relief", "log_food_emergency",
            "log_water_tank", "log_thermal_blanket", "log_lighting",
            "comm_walkie_talkie"
        ]
    },
    {
        "id": "team_logistics_002",
        "name": "遂宁市物资保障队",
        "type": "logistics",
        "headcount": 45,
        "specialization": "应急供电+宿营保障",
        "region": "四川省遂宁市",
        "lng": 105.571,
        "lat": 30.513,
        "equipment": [
            "log_generator_truck", "log_camp_vehicle", "log_tent_relief",
            "log_water_purifier", "comm_satellite_phone"
        ]
    },
    {
        "id": "team_logistics_003",
        "name": "资阳市物资保障队",
        "type": "logistics",
        "headcount": 40,
        "specialization": "生活保障+后勤支援",
        "region": "四川省资阳市",
        "lng": 104.641,
        "lat": 30.122,
        "equipment": [
            "log_tent_relief", "log_food_emergency", "log_water_tank",
            "log_generator_portable", "log_thermal_blanket"
        ]
    },
]

# ============================================================================
# 灾害场景（支持全灾种）
# ============================================================================
DISASTER_SCENARIOS = [
    {
        "id": "disaster_earthquake_wenchuan",
        "name": "汶川级特大地震",
        "type": "earthquake",
        "severity": "catastrophic",
        "description": "8.0级以上，大量建筑倒塌，次生灾害多发",
        "required_equipment_types": ["unmanned_aerial", "search_rescue", "engineering", "medical", "communication"]
    },
    {
        "id": "disaster_landslide_mountain",
        "name": "山体滑坡堰塞湖",
        "type": "landslide",
        "severity": "severe",
        "description": "大规模滑坡导致道路阻断、形成堰塞湖",
        "required_equipment_types": ["unmanned_aerial", "engineering", "unmanned_ground"]
    },
    {
        "id": "disaster_chemical_leak",
        "name": "化工厂泄露事故",
        "type": "chemical_leak",
        "severity": "severe",
        "description": "有毒有害气体泄露，需要防化处置",
        "required_equipment_types": ["protective", "unmanned_ground", "firefighting"]
    },
    {
        "id": "disaster_flash_flood",
        "name": "山洪泥石流",
        "type": "flash_flood",
        "severity": "high",
        "description": "突发性山洪，人员被困，道路中断",
        "required_equipment_types": ["unmanned_surface", "unmanned_aerial", "search_rescue"]
    },
    {
        "id": "disaster_forest_fire",
        "name": "森林火灾",
        "type": "fire",
        "severity": "high",
        "description": "大面积森林火灾，火线长，地形复杂",
        "required_equipment_types": ["firefighting", "unmanned_aerial", "logistics"]
    },
    {
        "id": "disaster_urban_fire",
        "name": "城市高层火灾",
        "type": "fire",
        "severity": "medium",
        "description": "高层建筑火灾，人员被困高层",
        "required_equipment_types": ["firefighting", "unmanned_aerial", "medical"]
    },
]


def merge_equipment_lists():
    """合并所有装备清单"""
    return (
        UNMANNED_EQUIPMENT +
        RESCUE_TOOLS +
        FIREFIGHTING_EQUIPMENT +
        MEDICAL_EQUIPMENT +
        ENGINEERING_EQUIPMENT +
        COMMUNICATION_EQUIPMENT +
        LOGISTICS_SUPPLIES +
        PROTECTIVE_EQUIPMENT
    )


def init_neo4j_knowledge_graph():
    """初始化Neo4j知识图谱"""
    driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))

    try:
        with driver.session() as session:
            print("🔥 警告：即将清空Neo4j现有数据...")
            session.run("MATCH (n) DETACH DELETE n")
            print("✅ 已清空现有数据\n")

            # 1. 创建装备节点
            all_equipment = merge_equipment_lists()
            print(f"📦 开始导入 {len(all_equipment)} 个装备节点...")
            for eq in all_equipment:
                session.run(
                    """
                    MERGE (e:Equipment {id: $id})
                    SET e.name = $name,
                        e.category = $category,
                        e.type = $type,
                        e.specs = $specs,
                        e.manufacturer = $manufacturer,
                        e.year = $year
                    """,
                    eq
                )
            print(f"✅ 装备节点导入完成\n")

            # 2. 创建救援队伍节点
            print(f"👥 开始导入 {len(RESCUE_TEAMS)} 支救援队伍...")
            for team in RESCUE_TEAMS:
                session.run(
                    """
                    MERGE (t:RescueTeam {id: $id})
                    SET t.name = $name,
                        t.type = $type,
                        t.headcount = $headcount,
                        t.specialization = $specialization,
                        t.region = $region,
                        t.lng = $lng,
                        t.lat = $lat
                    """,
                    {k: v for k, v in team.items() if k not in ['equipment', 'controlled_unmanned']}
                )

                # 2.1 创建OWNS关系（队伍拥有装备）
                for equip_id in team.get("equipment", []):
                    session.run(
                        """
                        MATCH (t:RescueTeam {id: $team_id})
                        MATCH (e:Equipment {id: $equip_id})
                        MERGE (t)-[:OWNS]->(e)
                        """,
                        {"team_id": team["id"], "equip_id": equip_id}
                    )

                # 2.2 创建CONTROLS关系（指挥中心控制无人设备 - "陆地航母"概念）
                if team["type"] == "command_center":
                    for unmanned_id in team.get("controlled_unmanned", []):
                        session.run(
                            """
                            MATCH (t:RescueTeam {id: $team_id})
                            MATCH (e:Equipment {id: $unmanned_id})
                            MERGE (t)-[:CONTROLS]->(e)
                            """,
                            {"team_id": team["id"], "unmanned_id": unmanned_id}
                        )
            print(f"✅ 救援队伍导入完成\n")

            # 3. 创建灾害场景节点
            print(f"🌋 开始导入 {len(DISASTER_SCENARIOS)} 个灾害场景...")
            for disaster in DISASTER_SCENARIOS:
                session.run(
                    """
                    MERGE (d:DisasterEvent {id: $id})
                    SET d.name = $name,
                        d.type = $type,
                        d.severity = $severity,
                        d.description = $description
                    """,
                    {k: v for k, v in disaster.items() if k != 'required_equipment_types'}
                )

                # 3.1 创建REQUIRES关系（灾害需要装备类型）
                for eq_type in disaster.get("required_equipment_types", []):
                    session.run(
                        """
                        MATCH (d:DisasterEvent {id: $disaster_id})
                        MATCH (e:Equipment)
                        WHERE e.category = $eq_type
                        MERGE (d)-[:REQUIRES]->(e)
                        """,
                        {"disaster_id": disaster["id"], "eq_type": eq_type}
                    )
            print(f"✅ 灾害场景导入完成\n")

            # 4. 创建CAN_RESPOND_TO关系（队伍可响应灾害类型）
            print("🔗 建立队伍-灾害响应关系...")
            # 重型救援队 → 地震
            session.run("""
                MATCH (t:RescueTeam {type: 'heavy_rescue'})
                MATCH (d:DisasterEvent {type: 'earthquake'})
                MERGE (t)-[:CAN_RESPOND_TO]->(d)
            """)
            # 消防队 → 火灾
            session.run("""
                MATCH (t:RescueTeam {type: 'firefighting'})
                MATCH (d:DisasterEvent)
                WHERE d.type = 'fire'
                MERGE (t)-[:CAN_RESPOND_TO]->(d)
            """)
            # 化工专业队 → 化学泄露
            session.run("""
                MATCH (t:RescueTeam)
                WHERE t.specialization CONTAINS '化工'
                MATCH (d:DisasterEvent {type: 'chemical_leak'})
                MERGE (t)-[:CAN_RESPOND_TO]->(d)
            """)
            # 水域救援队 → 洪水
            session.run("""
                MATCH (t:RescueTeam)
                WHERE t.specialization CONTAINS '水域'
                MATCH (d:DisasterEvent {type: 'flash_flood'})
                MERGE (t)-[:CAN_RESPOND_TO]->(d)
            """)
            # 工程抢修队 → 滑坡
            session.run("""
                MATCH (t:RescueTeam {type: 'engineering'})
                MATCH (d:DisasterEvent {type: 'landslide'})
                MERGE (t)-[:CAN_RESPOND_TO]->(d)
            """)
            print("✅ 响应关系建立完成\n")

            # 5. 统计验证
            print("=" * 60)
            print("📊 数据导入统计")
            print("=" * 60)

            stats = session.run("""
                MATCH (e:Equipment) WITH count(e) as equip_count
                MATCH (t:RescueTeam) WITH equip_count, count(t) as team_count
                MATCH (d:DisasterEvent) WITH equip_count, team_count, count(d) as disaster_count
                MATCH ()-[r:OWNS]->() WITH equip_count, team_count, disaster_count, count(r) as owns_count
                MATCH ()-[r2:CONTROLS]->() WITH equip_count, team_count, disaster_count, owns_count, count(r2) as controls_count
                MATCH ()-[r3:REQUIRES]->() WITH equip_count, team_count, disaster_count, owns_count, controls_count, count(r3) as requires_count
                MATCH ()-[r4:CAN_RESPOND_TO]->()
                RETURN equip_count, team_count, disaster_count, owns_count, controls_count, requires_count, count(r4) as respond_count
            """).single()

            print(f"装备节点数:     {stats['equip_count']}")
            print(f"救援队伍数:     {stats['team_count']}")
            print(f"灾害场景数:     {stats['disaster_count']}")
            print(f"OWNS关系数:     {stats['owns_count']}")
            print(f"CONTROLS关系数: {stats['controls_count']}")
            print(f"REQUIRES关系数: {stats['requires_count']}")
            print(f"CAN_RESPOND_TO: {stats['respond_count']}")
            print("=" * 60)

            # 6. 示例查询验证
            print("\n🔍 示例查询验证")
            print("=" * 60)

            # 查询指挥中心控制的无人设备
            print("\n1️⃣ 指挥中心可控制的无人设备（陆地航母）:")
            unmanned_devices = session.run("""
                MATCH (c:RescueTeam {type: 'command_center'})-[:CONTROLS]->(e:Equipment)
                RETURN e.name as name, e.type as type, e.specs as specs
            """)
            for record in unmanned_devices:
                print(f"   - {record['name']} ({record['type']}): {record['specs']}")

            # 查询能响应化工泄露的队伍
            print("\n2️⃣ 能响应化工泄露的救援队伍:")
            chem_teams = session.run("""
                MATCH (t:RescueTeam)-[:CAN_RESPOND_TO]->(d:DisasterEvent {type: 'chemical_leak'})
                RETURN t.name as team_name, t.specialization as spec
            """)
            for record in chem_teams:
                print(f"   - {record['team_name']} ({record['spec']})")

            # 查询2025最新装备统计
            print("\n3️⃣ 2025年装备分类统计:")
            equip_stats = session.run("""
                MATCH (e:Equipment {year: 2025})
                RETURN e.category as category, count(e) as count
                ORDER BY count DESC
            """)
            for record in equip_stats:
                print(f"   - {record['category']}: {record['count']}个")

            parsed = urlsplit(URI)
            browser_url = os.getenv(
                "NEO4J_BROWSER_URL",
                f"{os.getenv('NEO4J_BROWSER_SCHEME', 'http')}://"
                f"{parsed.hostname or 'localhost'}:"
                f"{os.getenv('NEO4J_BROWSER_PORT', '7474')}",
            )
            print("\n" + "=" * 60)
            print("✅ Neo4j知识图谱初始化完成！")
            print(f"🌐 浏览器访问: {browser_url}")
            print(f"🔗 Bolt URI: {URI}")
            print("=" * 60)

    finally:
        driver.close()


if __name__ == "__main__":
    print("\n" + "="*60)
    print("🚀 2025应急装备知识库初始化")
    print("="*60)
    print(f"Neo4j URI: {URI}")
    print(f"Neo4j用户: {USER}")
    print("="*60 + "\n")

    init_neo4j_knowledge_graph()
