# Copyright 2025 msq
from __future__ import annotations

from emergency_agents.config import AppConfig
from neo4j import GraphDatabase


SEED_CYPHER = [
    "CREATE CONSTRAINT hazard_name IF NOT EXISTS FOR (h:Hazard) REQUIRE h.name IS UNIQUE",
    "CREATE CONSTRAINT disaster_name IF NOT EXISTS FOR (d:Disaster) REQUIRE d.name IS UNIQUE",
    "CREATE CONSTRAINT equip_name IF NOT EXISTS FOR (e:Equipment) REQUIRE e.name IS UNIQUE",
    "CREATE CONSTRAINT env_name IF NOT EXISTS FOR (n:Environment) REQUIRE n.name IS UNIQUE",
    "CREATE CONSTRAINT facility_name IF NOT EXISTS FOR (f:Facility) REQUIRE f.name IS UNIQUE",
    
    "MERGE (:Disaster {name:'earthquake', display_name:'地震'})",
    "MERGE (:Disaster {name:'flood', display_name:'洪水'})",
    "MERGE (:Disaster {name:'landslide', display_name:'山体滑坡'})",
    "MERGE (:Disaster {name:'chemical_leak', display_name:'化工泄露'})",
    "MERGE (:Disaster {name:'fire', display_name:'火灾'})",
    
    "MERGE (:Facility {name:'reservoir', display_name:'水库', type:'water'})",
    "MERGE (:Facility {name:'chemical_plant', display_name:'化工厂', type:'industrial'})",
    "MERGE (:Facility {name:'mountain_area', display_name:'山区', type:'geological'})",
    
    """
    MATCH (eq:Disaster {name:'earthquake'}), (fl:Disaster {name:'flood'})
    MERGE (eq)-[:TRIGGERS {
        probability: 0.75, 
        delay_hours: 2, 
        condition: 'magnitude>7.0 AND nearby_reservoir',
        severity_factor: 1.5
    }]->(fl)
    """,
    
    """
    MATCH (eq:Disaster {name:'earthquake'}), (ls:Disaster {name:'landslide'})
    MERGE (eq)-[:TRIGGERS {
        probability: 0.85, 
        delay_hours: 1, 
        condition: 'magnitude>6.5 AND nearby_mountain',
        severity_factor: 1.3
    }]->(ls)
    """,
    
    """
    MATCH (eq:Disaster {name:'earthquake'}), (cl:Disaster {name:'chemical_leak'})
    MERGE (eq)-[:TRIGGERS {
        probability: 0.60, 
        delay_hours: 3, 
        condition: 'magnitude>7.0 AND nearby_chemical_plant',
        severity_factor: 2.0
    }]->(cl)
    """,
    
    """
    MATCH (fl:Disaster {name:'flood'}), (cl:Disaster {name:'chemical_leak'})
    MERGE (fl)-[:COMPOUNDS {
        severity_multiplier: 2.5, 
        type: 'toxic_spread',
        description: '洪水扩散化学污染'
    }]->(cl)
    """,
    
    """
    MERGE (:Equipment {name:'life_detector', display_name:'生命探测仪', category:'search'})
    """,
    """
    MERGE (:Equipment {name:'rescue_boat', display_name:'救援艇', category:'water_rescue'})
    """,
    """
    MERGE (:Equipment {name:'hazmat_suit', display_name:'防化服', category:'protection'})
    """,
    """
    MERGE (:Equipment {name:'gas_detector', display_name:'气体检测仪', category:'detection'})
    """,
    
    """
    MATCH (d:Disaster {name:'flood'}), (e:Equipment {name:'rescue_boat'})
    MERGE (d)-[:REQUIRES {quantity: 10, urgency: 'high'}]->(e)
    """,
    """
    MATCH (d:Disaster {name:'chemical_leak'}), (e:Equipment {name:'hazmat_suit'})
    MERGE (d)-[:REQUIRES {quantity: 50, urgency: 'critical'}]->(e)
    """,
    """
    MATCH (d:Disaster {name:'chemical_leak'}), (e:Equipment {name:'gas_detector'})
    MERGE (d)-[:REQUIRES {quantity: 20, urgency: 'high'}]->(e)
    """,
    
    "MERGE (:Hazard {name:'火灾'})",
    "MERGE (:Environment {name:'室内'})",
    "MERGE (:Equipment {name:'消防水带'})",
    "MERGE (:Equipment {name:'呼吸器'})",
    "MATCH (h:Hazard {name:'火灾'}), (e1:Equipment {name:'消防水带'}) MERGE (h)-[:MITIGATED_BY]->(e1)",
    "MATCH (e1:Equipment {name:'消防水带'}), (env:Environment {name:'室内'}) MERGE (e1)-[:SUITABLE_FOR {score:1.0}]->(env)",
    
    """
    MERGE (c:Case {id:'wenchuan_2008'}) 
    SET c.title='2008年汶川地震次生灾害', 
        c.summary='7.8级地震触发山体滑坡、堰塞湖等次生灾害',
        c.date='2008-05-12',
        c.casualties=69227
    """,
    """
    MATCH (c:Case {id:'wenchuan_2008'}), (d:Disaster {name:'earthquake'})
    MERGE (c)-[:INVOLVED]->(d)
    """,
    """
    MATCH (c:Case {id:'wenchuan_2008'}), (d:Disaster {name:'landslide'})
    MERGE (c)-[:INVOLVED]->(d)
    """,
    """
    MATCH (c:Case {id:'wenchuan_2008'}), (e:Equipment {name:'life_detector'})
    MERGE (c)-[:USED]->(e)
    """,
]


def main() -> None:
    cfg = AppConfig.load_from_env()
    uri = cfg.neo4j_uri or "bolt://localhost:7687"
    user = cfg.neo4j_user or "neo4j"
    # pragma: allowlist secret - placeholder credential for development
    password = cfg.neo4j_password or "example-neo4j"
    driver = GraphDatabase.driver(uri, auth=(user, password))
    with driver.session() as session:
        for stmt in SEED_CYPHER:
            session.run(stmt)
    driver.close()
    print("✅ Knowledge Graph seed data loaded successfully")


if __name__ == "__main__":
    main()
