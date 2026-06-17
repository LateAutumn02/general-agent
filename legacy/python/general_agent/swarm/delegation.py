"""Task delegation engine — keyword rules + LLM fallback.

Reference: ccswarm crates/ccswarm/src/orchestrator/master_delegation.rs
"""

from __future__ import annotations

import logging

from general_agent.swarm.types import (
    AgentDefinition,
    AgentPersonality,
    AgentRole,
    DelegationCondition,
    DelegationDecision,
    DelegationRule,
    SwarmTask,
)

logger = logging.getLogger("general_agent.swarm.delegation")

# ---------------------------------------------------------------------------
# Default delegation rules (matching ccswarm's hardcoded rules)
# ---------------------------------------------------------------------------

DEFAULT_RULES: list[DelegationRule] = [
    DelegationRule(
        name="Frontend UI Tasks",
        priority=10,
        keywords=["html", "css", "javascript", "ui", "component",
                   "前端", "界面", "页面", "react", "vue", "angular",
                   "typescript", "jsx", "样式", "布局"],
        target_role="Frontend",
    ),
    DelegationRule(
        name="Backend API Tasks",
        priority=11,
        keywords=["api", "server", "database", "backend", "endpoint",
                   "后端", "数据库", "接口", "rest", "crud", "express",
                   "fastapi", "django", "sql", "orm", "认证", "授权"],
        target_role="Backend",
    ),
    DelegationRule(
        name="Testing Tasks",
        priority=9,
        keywords=["test", "testing", "qa", "quality", "validation",
                   "测试", "单元测试", "集成测试", "e2e", "coverage",
                   "pytest", "jest", "vitest"],
        target_role="QA",
    ),
    DelegationRule(
        name="Infrastructure Tasks",
        priority=9,
        keywords=["deploy", "ci/cd", "docker", "infrastructure", "pipeline",
                   "部署", "容器", "k8s", "kubernetes", "nginx",
                   "github actions", "jenkins", "监控", "日志"],
        target_role="DevOps",
    ),
]

# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class MasterDelegationEngine:
    """Rule-based task delegation with optional LLM fallback.

    Rules are checked in priority order. If no rule matches, an optional
    LLM-based classifier can be invoked.
    """

    def __init__(self, rules: list[DelegationRule] | None = None) -> None:
        self._rules = sorted(rules or DEFAULT_RULES, key=lambda r: -r.priority)

    @property
    def rules(self) -> list[DelegationRule]:
        return list(self._rules)

    def add_rule(self, rule: DelegationRule) -> None:
        self._rules.append(rule)
        self._rules.sort(key=lambda r: -r.priority)

    def remove_rule(self, name: str) -> None:
        self._rules = [r for r in self._rules if r.name != name]

    # ---- matching ----

    def match(self, task: SwarmTask, available_roles: list[str]) -> DelegationDecision | None:
        """Try to match a task to an available agent role via rules."""
        desc_lower = task.description.lower()
        for rule in self._rules:
            # Check target role exists
            if rule.target_role not in available_roles:
                continue
            # Check keywords
            keyword_match = any(kw.lower() in desc_lower for kw in rule.keywords)
            if not keyword_match:
                continue
            # Check conditions
            if not self._check_conditions(rule.conditions, task):
                continue
            confidence = min(0.9, 0.5 + 0.05 * rule.priority)
            return DelegationDecision(
                task_id=task.task_id,
                target_role=rule.target_role,
                confidence=confidence,
                reasoning=f"Matched rule: {rule.name} (priority={rule.priority})",
                source="rule",
            )
        return None

    def _check_conditions(self, conditions: list[DelegationCondition], task: SwarmTask) -> bool:
        for cond in conditions:
            val = task.description if cond.field == "description" else getattr(task, cond.field, "")
            val_str = str(val).lower()
            target = str(cond.value).lower()
            if cond.op == "contains" and target not in val_str:
                return False
            if cond.op == "equals" and val_str != target:
                return False
        return True

    # ---- LLM fallback ----

    async def classify_with_llm(
        self, task: SwarmTask, available_agents: list[AgentDefinition],
    ) -> DelegationDecision:
        """Use LLM to classify which agent should handle this task."""
        agent_list = "\n".join(
            f"- {a.role.kind}: {', '.join(a.role.responsibilities[:3]) or 'general'}"
            for a in available_agents
        )
        prompt = (
            f"You are a task router. Given a task description and available agent types, "
            f"choose the best agent to handle it.\n\n"
            f"Task: {task.description}\n\n"
            f"Available agents:\n{agent_list}\n\n"
            f"Reply with ONLY the agent kind (one word): Frontend, Backend, DevOps, QA, or GeneralPurpose."
        )

        try:
            from general_agent.services.api.messages import query_model_simple
            response = await query_model_simple(prompt, max_tokens=20)
            role = response.strip().split("\n")[0].strip()
            # Validate
            valid_roles = {a.role.kind for a in available_agents}
            if role not in valid_roles:
                role = next(iter(valid_roles), "GeneralPurpose")
            return DelegationDecision(
                task_id=task.task_id,
                target_role=role,
                confidence=0.6,
                reasoning=f"LLM classified as: {role}",
                source="llm",
            )
        except Exception as e:
            logger.warning("LLM delegation fallback failed: %s", e)
            # Ultimate fallback
            return DelegationDecision(
                task_id=task.task_id,
                target_role=available_agents[0].role.kind if available_agents else "GeneralPurpose",
                confidence=0.1,
                reasoning=f"LLM fallback failed: {e}",
                source="fallback",
            )

    async def decompose_and_create(
        self, task_description: str,
    ) -> list[AgentDefinition]:
        """Let the LLM decompose a task and dynamically create the needed agents.

        The model decides:
        - How many agents are needed
        - What role each agent plays (custom names)
        - What each agent's responsibilities and boundaries are
        - How to split the work

        Returns a list of AgentDefinition ready to be instantiated.
        """
        prompt = (
            'Decompose this task into sub-tasks for 2-3 specialized agents.\n'
            f'TASK: {task_description}\n\n'
            'Return ONLY JSON like this example:\n'
            '{"agents":[{"name":"db","kind":"DatabaseDesigner",'
            '"responsibilities":["design schema"],"boundaries":["no UI"],'
            '"technologies":["SQL"],"task":"design the DB schema","depends_on":[]}]}'
        )

        try:
            import json as _json
            import re as _re
            from general_agent.services.api.messages import query_model_simple

            response = await query_model_simple(prompt, max_tokens=800)
            logger.info("LLM decompose raw response: %s", repr(response[:300]))

            # Try to extract & parse JSON
            data = None
            for extractor in (
                lambda r: _re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", r),
                lambda r: _re.search(r"```(?:json)?\s*(\[[\s\S]*?\])\s*```", r),
            ):
                m = extractor(response)
                if m:
                    try:
                        data = _json.loads(m.group(1))
                        if isinstance(data, list):  # model returned [...] instead of {agents: [...]}
                            data = {"agents": data}
                    except _json.JSONDecodeError:
                        pass
                    if data:
                        break

            if data is None:
                data = _extract_json_object(response)
                if data is None:
                    # Try parsing the whole response as a JSON array
                    stripped = response.strip()
                    if stripped.startswith("[") and stripped.endswith("]"):
                        try:
                            arr = _json.loads(stripped)
                            if isinstance(arr, list):
                                data = {"agents": arr}
                        except _json.JSONDecodeError:
                            pass

            if data is None:
                logger.warning("LLM decompose failed, using keyword-based fallback")
                return _fallback_multi_agent(task_description)

            agent_specs = data.get("agents", [])
            if not agent_specs:
                logger.warning("LLM decompose: empty agents, using keyword fallback")
                return _fallback_multi_agent(task_description)

            definitions: list[AgentDefinition] = []
            for spec in agent_specs:
                role = AgentRole(
                    kind=spec.get("kind", "GeneralPurpose"),
                    technologies=spec.get("technologies", []),
                    responsibilities=spec.get("responsibilities", []),
                    boundaries=spec.get("boundaries", []),
                )
                sub_task = spec.get("task", task_description)
                deps = spec.get("depends_on", [])

                definition = AgentDefinition(
                    name=spec.get("name", f"agent-{len(definitions)}"),
                    role=role,
                    system_prompt=(
                        f"You are a {role.kind} specialist.\n"
                        f"Your task: {sub_task}\n"
                        f"Responsibilities: {', '.join(role.responsibilities)}\n"
                        f"Boundaries (do NOT touch): {', '.join(role.boundaries)}"
                    ),
                    max_turns=15,
                )
                # Attach task metadata for the coordinator
                definition._sub_task = sub_task  # type: ignore[attr-defined]
                definition._depends_on = deps  # type: ignore[attr-defined]
                definitions.append(definition)

            logger.info("LLM decomposed task into %d agent(s): %s",
                        len(definitions),
                        [(d.name, d.role.kind) for d in definitions])
            return definitions

        except Exception as e:
            logger.warning("LLM decompose failed: %s, falling back", e)
            return [_fallback_agent(task_description)]

    async def delegate(
        self, task: SwarmTask, available_agents: list[AgentDefinition],
    ) -> DelegationDecision:
        """Full delegation pipeline: rule match → LLM fallback."""
        available_roles = list({a.role.kind for a in available_agents})
        if task.target_role and task.target_role in available_roles:
            return DelegationDecision(
                task_id=task.task_id,
                target_role=task.target_role,
                confidence=1.0,
                reasoning="User-specified target role",
                source="user",
            )
        decision = self.match(task, available_roles)
        if decision:
            return decision
        return await self.classify_with_llm(task, available_agents)


def _extract_json_object(text: str) -> dict | None:
    """Extract the outermost balanced JSON object from text."""
    import json as _json
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return _json.loads(text[start:i + 1])
                except _json.JSONDecodeError:
                    return None
    return None


def _fallback_agent(task_description: str) -> AgentDefinition:
    """Single GeneralPurpose agent as ultimate fallback."""
    return AgentDefinition(
        name="general",
        role=AgentRole(kind="GeneralPurpose",
                       responsibilities=["Handle any task"]),
        system_prompt=f"Complete this task: {task_description}",
    )


def _fallback_multi_agent(task_description: str) -> list[AgentDefinition]:
    """Create 2 agents based on task keywords when LLM decomposition fails."""
    desc_lower = task_description.lower()

    # Detect domains from keywords
    has_frontend = any(kw in desc_lower for kw in
                       ["前端", "ui", "界面", "页面", "frontend", "react", "vue", "css", "html", "组件"])
    has_backend = any(kw in desc_lower for kw in
                      ["后端", "api", "数据库", "backend", "server", "sql", "接口", "认证", "auth"])
    has_data = any(kw in desc_lower for kw in
                   ["数据", "分析", "调研", "research", "analysis", "data", "比较", "对比", "compare"])
    has_test = any(kw in desc_lower for kw in
                   ["测试", "test", "qa", "质量"])

    agents: list[AgentDefinition] = []

    if has_data or (not has_frontend and not has_backend):
        # Research/comparison task → 2 researchers + 1 synthesizer
        agents.append(AgentDefinition(
            name="researcher_a",
            role=AgentRole(kind="Researcher", responsibilities=["Research and gather facts"],
                           boundaries=["Do not draw conclusions — just gather data"]),
            system_prompt=(
                f"You are Researcher A. For this task: '{task_description}'\n"
                "Gather facts, data, and evidence from one perspective. "
                "Be thorough and cite sources when possible. "
                "When you find something useful, share it via whiteboard so Researcher B can build on it.\n"
                "After completing your research, send a message to Researcher B via the coordinator "
                "summarizing your key findings."
            ),
            max_turns=10,
        ))
        agents.append(AgentDefinition(
            name="researcher_b",
            role=AgentRole(kind="Researcher", responsibilities=["Research complementary angle"],
                           boundaries=["Do not repeat Researcher A's findings"]),
            system_prompt=(
                f"You are Researcher B. For this task: '{task_description}'\n"
                "Research from a DIFFERENT angle than typical. Look for contrarian views, "
                "edge cases, or alternative approaches.\n"
                "Read Researcher A's whiteboard entries before starting — build on their work, don't duplicate.\n"
                "After your research, send your findings to Researcher A for cross-validation."
            ),
            max_turns=10,
        ))
        # Researcher B depends on Researcher A's whiteboard
        agents[1]._depends_on = ["researcher_a"]  # type: ignore[attr-defined]

    if has_frontend or has_backend:
        if has_backend:
            agents.append(AgentDefinition(
                name="backend_dev",
                role=AgentRole(kind="Backend", responsibilities=["Backend implementation"],
                               technologies=["Python", "API"]),
                system_prompt=f"Backend specialist. Task: {task_description}. Focus on server-side logic.",
                max_turns=10,
            ))
        if has_frontend:
            agents.append(AgentDefinition(
                name="frontend_dev",
                role=AgentRole(kind="Frontend", responsibilities=["Frontend implementation"],
                               technologies=["HTML", "CSS", "JS"]),
                system_prompt=f"Frontend specialist. Task: {task_description}. Focus on UI/UX.",
                max_turns=10,
            ))
        # Frontend depends on Backend if both exist
        if has_frontend and has_backend:
            for a in agents:
                if a.name == "frontend_dev":
                    a._depends_on = ["backend_dev"]  # type: ignore[attr-defined]

    if has_test:
        agents.append(AgentDefinition(
            name="qa_tester",
            role=AgentRole(kind="QA", responsibilities=["Test and validate"]),
            system_prompt=f"QA specialist. Task: {task_description}. Write tests and validate.",
            max_turns=10,
        ))

    if not agents:
        agents.append(_fallback_agent(task_description))

    # Assign sub-tasks
    for i, a in enumerate(agents):
        a._sub_task = f"Agent {i+1} ({a.role.kind}): {task_description}"  # type: ignore[attr-defined]

    return agents

