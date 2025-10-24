# Copyright 2025 msq
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from neo4j import GraphDatabase


@dataclass
class KGConfig:
	"""图服务配置。

	Args:
		uri: Neo4j bolt 地址。
		user: 用户名。
		password: 密码。
	"""
	uri: str
	user: str
	password: str


class KGService:
	"""知识图谱服务。

	提供装备推荐与案例检索。
	"""

	def __init__(self, cfg: KGConfig) -> None:
		self._driver = GraphDatabase.driver(cfg.uri, auth=(cfg.user, cfg.password))

	def close(self) -> None:
		self._driver.close()

	def recommend_equipment(self, *, hazard: str, environment: Optional[str] = None, top_k: int = 5) -> List[Dict[str, Any]]:
		"""基于危害/环境推荐装备。

		Args:
			hazard: 危害类型（如“火灾”、“有毒气体”）。
			environment: 环境（如“室内”、“隧道”）。
			top_k: 返回数量。

		Returns:
			装备列表，含名称与证据边信息。
		"""
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
			return [{"name": r["name"], "score": r["score"]} for r in rows]

	def search_cases(self, *, keywords: str, top_k: int = 5) -> List[Dict[str, Any]]:
		"""按关键词检索救援案例。

		Args:
			keywords: 关键字（支持简单包含匹配）。
			top_k: 返回数量。

		Returns:
			案例列表，含标题与关联装备。
		"""
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
			return [{"id": r["id"], "title": r["title"], "equipments": r["equipments"]} for r in rows]

	def predict_secondary_disasters(self, *, primary_disaster: str, magnitude: float = 0.0) -> List[Dict[str, Any]]:
		"""预测次生灾害。

		Args:
			primary_disaster: 主要灾害类型（如"earthquake"）。
			magnitude: 灾害强度（如地震震级）。

		Returns:
			次生灾害列表，含类型、概率、延迟时间等。
		
		Reference: docs/分析报告 lines 248-254
		"""
		query = """
		MATCH (primary:Disaster {name: $disaster})-[t:TRIGGERS]->(secondary:Disaster)
		WHERE $magnitude >= 0.0
		RETURN 
			secondary.name AS type,
			secondary.display_name AS display_name,
			t.probability AS probability,
			t.delay_hours AS delay_hours,
			t.condition AS condition,
			t.severity_factor AS severity_factor
		ORDER BY t.probability DESC
		"""
		with self._driver.session() as session:
			rows = session.run(query, disaster=primary_disaster, magnitude=magnitude)
			return [dict(r) for r in rows]

	def get_compound_risks(self, *, disaster_ids: List[str]) -> List[Dict[str, Any]]:
		"""获取风险叠加效应。

		Args:
			disaster_ids: 活跃的灾害类型列表（如["flood", "chemical_leak"]）。

		Returns:
			复合风险列表，含叠加效应信息。
		
		Reference: docs/分析报告 lines 256-260
		"""
		query = """
		MATCH (d1:Disaster)-[c:COMPOUNDS]->(d2:Disaster)
		WHERE d1.name IN $ids AND d2.name IN $ids
		RETURN 
			d1.name AS source,
			d2.name AS target,
			c.type AS compound_type,
			c.severity_multiplier AS multiplier,
			c.description AS description
		"""
		with self._driver.session() as session:
			rows = session.run(query, ids=disaster_ids)
			return [dict(r) for r in rows]

	def get_equipment_requirements(self, *, disaster_types: List[str]) -> List[Dict[str, Any]]:
		"""获取装备需求。

		Args:
			disaster_types: 灾害类型列表（如["flood", "chemical_leak"]）。

		Returns:
			装备需求列表，含名称、数量、紧急程度。
		
		Reference: docs/分析报告 lines 262-268
		"""
		query = """
		MATCH (d:Disaster)-[r:REQUIRES]->(eq:Equipment)
		WHERE d.name IN $types
		RETURN 
			eq.name AS equipment_name,
			eq.display_name AS display_name,
			eq.category AS category,
			sum(r.quantity) AS total_quantity,
			max(r.urgency) AS max_urgency,
			collect(d.name) AS for_disasters
		ORDER BY max_urgency DESC, total_quantity DESC
		"""
		with self._driver.session() as session:
			rows = session.run(query, types=disaster_types)
			return [dict(r) for r in rows]


