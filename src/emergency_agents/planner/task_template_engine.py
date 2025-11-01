from __future__ import annotations

import heapq
from collections import defaultdict
from typing import Dict, Iterable, List, Sequence, Set, Tuple

from .models import HazardPack, MissionPhase, PlannedMission, PlannedTask, TaskTemplate


class TaskTemplateEngine:
    """任务模板解析引擎。"""

    def __init__(self, phase_priority: Sequence[MissionPhase] | None = None) -> None:
        self._phase_priority = list(phase_priority) if phase_priority else [
            MissionPhase.RECONNAISSANCE,
            MissionPhase.RESCUE,
            MissionPhase.ALERT,
            MissionPhase.LOGISTICS,
        ]
        self._phase_rank: Dict[MissionPhase, int] = {
            phase: index for index, phase in enumerate(self._phase_priority)
        }

    def build_plan(self, pack: HazardPack, severity_score: float) -> PlannedMission:
        """根据知识包生成任务计划。"""

        severity_label = pack.severity_label(severity_score)
        tasks = self._collect_tasks(pack)
        ordered = self._topological_sort(tasks)
        planned_tasks = [
            PlannedTask(
                task_id=item.task_id,
                phase=item.phase,
                task_type=item.task_type,
                required_capabilities=item.required_capabilities,
                recommended_equipment=item.recommended_equipment,
                duration_minutes=item.duration_minutes,
                dependencies=item.dependencies,
                parallel_allowed=item.parallel_allowed,
                description=item.description,
                safety_notes=item.safety_notes,
                severity_label=severity_label,
            )
            for item in ordered
        ]
        return PlannedMission(
            hazard_type=pack.hazard_type,
            severity_label=severity_label,
            tasks=planned_tasks,
            risk_rules=pack.risk_rules,
            reference_cases=pack.reference_cases,
        )

    def _collect_tasks(self, pack: HazardPack) -> List[TaskTemplate]:
        collected: List[TaskTemplate] = []
        for template in pack.mission_templates:
            for task in template.tasks:
                collected.append(task.model_copy(update={"phase": template.phase}))
        return collected

    def _topological_sort(self, tasks: Iterable[TaskTemplate]) -> List[TaskTemplate]:
        task_map: Dict[str, TaskTemplate] = {}
        indegree: Dict[str, int] = defaultdict(int)
        adjacency: Dict[str, List[str]] = defaultdict(list)

        for task in tasks:
            if task.task_id in task_map:
                raise ValueError(f"duplicate task_id detected: {task.task_id}")
            task_map[task.task_id] = task
            for dependency in task.dependencies:
                indegree[task.task_id] += 1
                adjacency[dependency].append(task.task_id)

        queue: List[Tuple[int, str]] = []
        for task_id, task in task_map.items():
            if indegree[task_id] == 0:
                heapq.heappush(queue, (self._phase_rank.get(task.phase, len(self._phase_priority)), task_id))

        ordered: List[TaskTemplate] = []
        visited: Set[str] = set()
        while queue:
            _, current = heapq.heappop(queue)
            visited.add(current)
            ordered.append(task_map[current])
            for neighbor in adjacency[current]:
                indegree[neighbor] -= 1
                if indegree[neighbor] == 0 and neighbor not in visited:
                    phase_rank = self._phase_rank.get(task_map[neighbor].phase, len(self._phase_priority))
                    heapq.heappush(queue, (phase_rank, neighbor))

        if len(ordered) != len(task_map):
            missing = set(task_map).difference({task.task_id for task in ordered})
            raise ValueError(f"task dependency cycle detected: {sorted(missing)}")
        return ordered
