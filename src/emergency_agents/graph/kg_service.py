# Copyright 2025 msq
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import structlog

from neo4j import GraphDatabase


@dataclass
class KGConfig:
    """图服务配置。"""

    uri: str
    user: str
    password: str


class KGService:
    """知识图谱服务，负责Neo4j查询。"""

    def __init__(self, cfg: KGConfig) -> None:
        self._driver = GraphDatabase.driver(cfg.uri, auth=(cfg.user, cfg.password))

    def close(self) -> None:
        self._driver.close()

    def get_equipment_requirements(self, disaster_types: List[str]) -> List[Dict[str, Any]]:
        query = """
        MATCH (d:DisasterEvent)-[r:REQUIRES]->(eq:Equipment)
        WHERE d.id IN $types OR d.name IN $types OR d.type IN $types
        WITH
            eq,
            collect(DISTINCT d) AS disasters,
            collect(
                CASE
                    WHEN 'quantity' IN keys(r) AND r.quantity IS NOT NULL
                        THEN toFloat(r.quantity)
                    ELSE 1.0
                END
            ) AS raw_quantities,
            collect(
                CASE
                    WHEN 'urgency' IN keys(r) AND r.urgency IS NOT NULL
                        THEN toFloat(r.urgency)
                    ELSE 0.0
                END
            ) AS raw_urgencies
        WITH
            eq,
            disasters,
            CASE
                WHEN size(raw_quantities) = 0
                    THEN 0.0
                ELSE reduce(total = 0.0, q IN raw_quantities | total + q)
            END AS total_quantity,
            CASE
                WHEN size(raw_urgencies) = 0
                    THEN 0.0
                ELSE reduce(maxu = 0.0, u IN raw_urgencies | CASE WHEN u > maxu THEN u ELSE maxu END)
            END AS max_urgency
        RETURN
            eq.id AS equipment_id,
            CASE
                WHEN 'display_name' IN keys(eq) AND eq.display_name IS NOT NULL
                    THEN eq.display_name
                ELSE eq.name
            END AS display_name,
            eq.name AS equipment_name,
            eq.category AS category,
            total_quantity AS total_quantity,
            max_urgency AS max_urgency,
            size(disasters) AS related_disasters,
            [d IN disasters | coalesce(d.id, d.name)] AS for_disasters
        ORDER BY total_quantity DESC, display_name
        """
        with self._driver.session() as session:
            rows = session.run(query, types=disaster_types)
            result = []
            for r in rows:
                data = dict(r)
                data["total_quantity"] = int(data.get("total_quantity") or 0)
                data["max_urgency"] = float(data.get("max_urgency") or 0)
                result.append(data)
            if result:
                return result

            fallback = session.run(
                """
                MATCH (eq:Equipment)<-[:OWNS]-(team:RescueTeam)
                WITH eq, collect(DISTINCT team) AS teams
                RETURN
                    eq.id AS equipment_id,
                    CASE
                        WHEN 'display_name' IN keys(eq) AND eq.display_name IS NOT NULL
                            THEN eq.display_name
                        ELSE eq.name
                    END AS display_name,
                    eq.name AS equipment_name,
                    eq.category AS category,
                    size(teams) AS total_quantity,
                    1.0 AS max_urgency,
                    size(teams) AS related_disasters,
                    [] AS for_disasters
                ORDER BY related_disasters DESC, display_name
                LIMIT 20
                """
            )
            result = []
            for r in fallback:
                data = dict(r)
                data["total_quantity"] = int(data.get("total_quantity") or 0)
                data["max_urgency"] = float(data.get("max_urgency") or 0)
                result.append(data)
            return result

    def predict_secondary_disasters(self, primary_disaster: str, magnitude: float = 0.0) -> List[Dict[str, Any]]:
        query = """
        MATCH (primary:DisasterEvent)-[t:TRIGGERS]->(secondary:DisasterEvent)
        WHERE (primary.id = $disaster OR primary.name = $disaster OR primary.type = $disaster)
          AND $magnitude >= 0.0
        RETURN 
            CASE
                WHEN 'name' IN keys(secondary) AND secondary.name IS NOT NULL
                    THEN secondary.name
                ELSE coalesce(secondary.id, secondary.type)
            END AS type,
            CASE
                WHEN 'display_name' IN keys(secondary) AND secondary.display_name IS NOT NULL
                    THEN secondary.display_name
                WHEN 'name' IN keys(secondary) AND secondary.name IS NOT NULL
                    THEN secondary.name
                ELSE coalesce(secondary.id, secondary.type)
            END AS display_name,
            CASE
                WHEN 'probability' IN keys(t) THEN toFloat(t.probability)
                ELSE NULL
            END AS probability,
            CASE
                WHEN 'delay_hours' IN keys(t) THEN toFloat(t.delay_hours)
                ELSE NULL
            END AS delay_hours,
            CASE
                WHEN 'condition' IN keys(t) THEN t.condition
                ELSE NULL
            END AS condition,
            CASE
                WHEN 'severity_factor' IN keys(t) THEN toFloat(t.severity_factor)
                ELSE NULL
            END AS severity_factor
        ORDER BY t.probability DESC
        """
        with self._driver.session() as session:
            rows = session.run(query, disaster=primary_disaster, magnitude=magnitude)
            return [dict(r) for r in rows]

    def get_compound_risks(self, disaster_ids: List[str]) -> List[Dict[str, Any]]:
        query = """
        MATCH (d1:DisasterEvent)-[c:COMPOUNDS]->(d2:DisasterEvent)
        WHERE (d1.id IN $ids OR d1.name IN $ids OR d1.type IN $ids)
          AND (d2.id IN $ids OR d2.name IN $ids OR d2.type IN $ids)
        RETURN 
            CASE
                WHEN 'name' IN keys(d1) AND d1.name IS NOT NULL
                    THEN d1.name
                ELSE coalesce(d1.id, d1.type)
            END AS source,
            CASE
                WHEN 'name' IN keys(d2) AND d2.name IS NOT NULL
                    THEN d2.name
                ELSE coalesce(d2.id, d2.type)
            END AS target,
            c.type AS compound_type,
            CASE
                WHEN 'severity_multiplier' IN keys(c) THEN toFloat(c.severity_multiplier)
                ELSE NULL
            END AS multiplier,
            CASE
                WHEN 'description' IN keys(c) THEN c.description
                ELSE NULL
            END AS description
        """
        with self._driver.session() as session:
            rows = session.run(query, ids=disaster_ids)
            return [dict(r) for r in rows]

    def recommend_equipment(self, hazard: str, environment: Optional[str] = None, top_k: int = 5) -> List[Dict[str, Any]]:
        query = (
            """
            MATCH (h:Hazard {name: $hazard})-[:MITIGATED_BY]->(e:Equipment)
            OPTIONAL MATCH (e)-[r:SUITABLE_FOR]->(env:Environment {name: $env})
            WITH e, r
            RETURN e.name AS name, coalesce(r.score, 1.0) AS score
            ORDER BY score DESC
            LIMIT $k
            """
        )
        with self._driver.session() as session:
            rows = session.run(query, hazard=hazard, env=environment, k=top_k)
            return [dict(r) for r in rows]


class DisabledKGService:
    """知识图谱关闭时的占位实现，阻止外部连接。"""

    def __init__(self) -> None:
        structlog.get_logger(__name__).warning("kg_disabled", reason="ENABLE_KG=false")

    def close(self) -> None:  # noqa: D401
        structlog.get_logger(__name__).info("kg_close_skipped_disabled")

    def get_equipment_requirements(self, disaster_types: List[str]) -> List[Dict[str, Any]]:
        structlog.get_logger(__name__).info(
            "kg_query_skipped_disabled",
            query="equipment_requirements",
            types=disaster_types,
        )
        return []

    def predict_secondary_disasters(self, primary_disaster: str, magnitude: float = 0.0) -> List[Dict[str, Any]]:
        structlog.get_logger(__name__).info(
            "kg_query_skipped_disabled",
            query="secondary_disasters",
            disaster=primary_disaster,
        )
        return []

    def get_compound_risks(self, disaster_ids: List[str]) -> List[Dict[str, Any]]:
        structlog.get_logger(__name__).info(
            "kg_query_skipped_disabled",
            query="compound_risks",
            ids=disaster_ids,
        )
        return []

    def recommend_equipment(self, hazard: str, environment: Optional[str] = None, top_k: int = 5) -> List[Dict[str, Any]]:
        structlog.get_logger(__name__).info(
            "kg_query_skipped_disabled",
            query="recommend_equipment",
            hazard=hazard,
            environment=environment,
            top_k=top_k,
        )
        return []

    def search_cases(self, keywords: str, top_k: int = 5) -> List[Dict[str, Any]]:
        query = (
            """
            MATCH (c:Case)
            WHERE toLower(c.title) CONTAINS toLower($kw) OR toLower(coalesce(c.summary,'')) CONTAINS toLower($kw)
            OPTIONAL MATCH (c)-[:USED]->(e:Equipment)
            WITH c, collect(DISTINCT e.name) AS equipments
            RETURN c.title AS title, c.id AS id, equipments AS equipments
            LIMIT $k
            """
        )
        with self._driver.session() as session:
            rows = session.run(query, kw=keywords, k=top_k)
            return [dict(r) for r in rows]
