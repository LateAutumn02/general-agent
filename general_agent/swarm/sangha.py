"""Sangha consensus — democratic voting for swarm decisions.

Simple majority voting + LLM tiebreaker.
Reference: ccswarm crates/ccswarm/src/cli/commands/sangha.rs (concept, stub)
"""

from __future__ import annotations

import asyncio
import logging

from general_agent.swarm.types import SanghaProposal, SanghaVote

logger = logging.getLogger("general_agent.swarm.sangha")

VOTE_TIMEOUT_S = 300  # 5 minutes


class Sangha:
    """Democratic decision-making for the swarm.

    Proposals are broadcast to all agents. Each agent votes based on
    its role expertise. Simple majority wins; LLM breaks ties.
    """

    def __init__(self) -> None:
        self._proposals: dict[str, SanghaProposal] = {}

    def propose(self, title: str, description: str, proposer_id: str = "user") -> SanghaProposal:
        proposal = SanghaProposal(
            title=title,
            description=description,
            proposer_id=proposer_id,
            status="Voting",
        )
        self._proposals[proposal.proposal_id] = proposal
        logger.info("Sangha proposal #%s: %s", proposal.proposal_id[:8], title)
        return proposal

    def vote(self, proposal_id: str, agent_id: str, vote: str,
             reason: str = "", weight: float = 1.0) -> SanghaVote:
        """Record a vote from an agent."""
        proposal = self._proposals.get(proposal_id)
        if not proposal or proposal.status != "Voting":
            raise ValueError(f"Proposal {proposal_id} is not open for voting")

        v = SanghaVote(agent_id=agent_id, vote=vote, reason=reason, weight=weight)
        proposal.votes.append(v)
        logger.info("Vote on #%s: %s → %s", proposal_id[:8], agent_id, vote)
        self._check_outcome(proposal)
        return v

    def _check_outcome(self, proposal: SanghaProposal) -> None:
        """Check if voting should conclude."""
        total_weight = sum(v.weight for v in proposal.votes)
        approve_weight = sum(v.weight for v in proposal.votes if v.vote == "Approve")
        reject_weight = sum(v.weight for v in proposal.votes if v.vote == "Reject")

        if total_weight == 0:
            return

        approve_pct = approve_weight / total_weight
        if approve_pct > 0.5:
            proposal.status = "Passed"
            logger.info("Proposal #%s PASSED (%.0f%%)", proposal.proposal_id[:8], approve_pct * 100)
        elif (1 - approve_pct - (sum(v.weight for v in proposal.votes
                                      if v.vote == "Abstain") / total_weight)) > 0.5:
            proposal.status = "Rejected"
            logger.info("Proposal #%s REJECTED", proposal.proposal_id[:8])

    async def break_tie(self, proposal: SanghaProposal) -> str:
        """Use LLM to break a voting tie."""
        if proposal.status in ("Passed", "Rejected"):
            return proposal.status

        approve = [v for v in proposal.votes if v.vote == "Approve"]
        reject = [v for v in proposal.votes if v.vote == "Reject"]

        prompt = (
            f"Proposal: {proposal.title}\n"
            f"Description: {proposal.description}\n\n"
            f"Approve reasons:\n" + "\n".join(f"- {v.reason}" for v in approve) + "\n\n"
            f"Reject reasons:\n" + "\n".join(f"- {v.reason}" for v in reject) + "\n\n"
            f"As a neutral tiebreaker, reply with only 'Approve' or 'Reject'."
        )

        try:
            from general_agent.services.api.messages import query_model_simple
            response = await query_model_simple(prompt, max_tokens=10)
            decision = response.strip().lower()
            if "approve" in decision:
                proposal.status = "Passed"
            else:
                proposal.status = "Rejected"
        except Exception as e:
            logger.warning("Tiebreaker failed: %s — defaulting to Passed", e)
            proposal.status = "Passed"

        return proposal.status

    def get_proposal(self, proposal_id: str) -> SanghaProposal | None:
        return self._proposals.get(proposal_id)

    def list_proposals(self, status: str = "") -> list[SanghaProposal]:
        if status:
            return [p for p in self._proposals.values() if p.status == status]
        return list(self._proposals.values())
