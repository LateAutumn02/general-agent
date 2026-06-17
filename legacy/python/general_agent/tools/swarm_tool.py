"""SwarmTool — spawn a swarm of sub-agents that communicate and collaborate.

The main agent calls this tool to delegate complex multi-agent tasks.
Unlike AgentTool (single fork), SwarmTool lets the LLM dynamically create
agents, split work, and run them in parallel with inter-agent communication.

Reference: ccswarm multi-agent orchestration pattern
"""

from __future__ import annotations

from typing import Any

from general_agent.tools.tool import Tool, ToolResult


class SwarmTool(Tool):
    """Launch a swarm of agents to handle a complex task collaboratively.

    The swarm coordinator uses LLM to:
    1. Decompose the task into sub-tasks
    2. Dynamically create specialized agents for each sub-task
    3. Execute them in dependency order (independent agents run in parallel)
    4. Aggregate results with quality review
    """

    name = "Swarm"

    def get_input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "description": {
                    "type": "string",
                    "description": "A short (3-5 word) description of the overall task",
                },
                "prompt": {
                    "type": "string",
                    "description": (
                        "The full task description. Be specific about what needs to be done. "
                        "The swarm will decompose this into sub-tasks and create specialized "
                        "agents to handle each part. For example: "
                        "'Add user authentication with JWT: design the database schema, "
                        "implement the login API, and create the login form UI.'"
                    ),
                },
                "max_agents": {
                    "type": "integer",
                    "description": "Maximum number of agents to spawn (default 5). Limits parallelism.",
                },
            },
            "required": ["description", "prompt"],
        }

    def is_read_only(self, args: dict[str, Any]) -> bool:
        return False

    def is_concurrency_safe(self, args: dict[str, Any]) -> bool:
        return True  # Swarm manages its own concurrency

    async def description(self, input: dict[str, Any] | None = None) -> str:
        if input:
            return input.get("description", "Launch a swarm of agents")
        return (
            "Launch a swarm of specialized agents to handle complex multi-step tasks. "
            "Agents communicate with each other and share context via a message bus. "
            "The swarm dynamically creates the right agents for the job."
        )

    async def prompt(self) -> str:
        return """Launch a swarm of collaborating agents for complex tasks.

When to use Swarm (instead of a single Agent):
- **Multi-domain tasks**: The task spans frontend + backend + database + deploy
- **Parallel work**: Multiple independent pieces can be done simultaneously
- **Peer review**: You want agents to review each other's work
- **Complex decomposition**: The task naturally breaks into sub-tasks with dependencies

When NOT to use Swarm:
- Simple single-file edits → use Edit/Write directly
- Single-domain research → use Agent
- Sequential steps that must be done in order → use Agent

What happens:
1. You provide a detailed task description
2. The swarm analyzes it and decides: how many agents, what roles, what each does
3. Agents are created dynamically with custom roles (e.g. "DatabaseDesigner", "AuthAPISpecialist")
4. Independent agents run in parallel; dependent agents wait
5. Agents can communicate via message bus (ask for help, share discoveries)
6. Results are aggregated with a quality review

Example:
```
prompt: "Add user authentication: design DB schema for users table,
         implement POST /login and POST /register endpoints,
         and create a login form component"
```
The swarm might create:
- DBSchemaDesigner → designs users table
- BackendAPIDeveloper → implements login/register endpoints (waits for DB schema)
- FrontendUIDeveloper → creates login form component (independent, runs parallel)"""

    async def call(
        self,
        args: dict[str, Any],
        context: Any = None,
        can_use_tool: Any = None,
        on_progress: Any = None,
    ) -> ToolResult:
        prompt_text = args["prompt"]
        max_agents = args.get("max_agents", 5)

        import os
        from general_agent.swarm import SwarmCoordinator

        coord = SwarmCoordinator(
            project_root=os.getcwd(),
            max_concurrent=min(max_agents, 5),
        )
        coord.start()

        try:
            # Hook tracer: always print to stderr for visibility, plus on_progress if available
            import sys as _sys
            coord.tracer.on_event(lambda e: (
                _sys.stderr.write(e.format() + "\n"),
                _sys.stderr.flush(),
                on_progress(e.format()) if on_progress else None,
            ))

            result = await coord.submit_task(
                prompt_text, dynamic=True,
                on_progress=on_progress,
                on_text=None,  # sub-agent text goes to tracer, not raw stream
            )

            # Collect output
            if isinstance(result, list):
                # Multi-agent result
                outputs = []
                total_duration = 0
                success_count = 0
                for r in result:
                    if r.status.value == "Completed":
                        success_count += 1
                        outputs.append(
                            f"[{r.agent_id[:8]}] {r.output[:500]}"
                        )
                    else:
                        outputs.append(
                            f"[{r.agent_id[:8]}] FAILED: {r.error}"
                        )
                    total_duration = max(total_duration, r.duration_ms)

                summary = (
                    f"Swarm completed: {success_count}/{len(result)} agents succeeded "
                    f"in {total_duration}ms\n\n" + "\n\n".join(outputs)
                )
                return ToolResult(data={
                    "agent_count": len(result),
                    "success_count": success_count,
                    "total_duration_ms": total_duration,
                    "output": summary,
                    "results": [
                        {
                            "agent_id": r.agent_id,
                            "status": r.status.value,
                            "output": r.output[:1000],
                            "quality_score": r.quality_score,
                            "duration_ms": r.duration_ms,
                        }
                        for r in result
                    ],
                })
            else:
                # Single agent result
                return ToolResult(data={
                    "agent_count": 1,
                    "success_count": 1 if result.status.value == "Completed" else 0,
                    "total_duration_ms": result.duration_ms,
                    "output": result.output,
                    "quality_score": result.quality_score,
                })

        finally:
            await coord.shutdown()

    def map_tool_result_to_block(self, output: Any, tool_use_id: str) -> dict:
        if isinstance(output, dict):
            text = output.get("output", "")
            agent_count = output.get("agent_count", 1)
            success = output.get("success_count", 0)
            prefix = f"[Swarm: {success}/{agent_count} agents] "
            full_text = prefix + str(text)
            if len(full_text) > 5000:
                full_text = full_text[:4997] + "..."
            is_error = success == 0
            return {
                "type": "tool_result",
                "tool_use_id": tool_use_id,
                "content": full_text,
                "is_error": is_error,
            }
        return {
            "type": "tool_result",
            "tool_use_id": tool_use_id,
            "content": str(output)[:5000],
            "is_error": False,
        }
