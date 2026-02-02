"""LLM State - Thread-safe shared state for HTTP visualization"""

from typing import Dict, Any, List, Optional


class LLMState:
    """
    Shared state between the LLM trainer (main thread) and HTTP server (background thread).

    The trainer writes to this state, and HTTP endpoints read from it.
    Since Python's GIL protects simple attribute assignments, this is
    safe for the read/write pattern used here.
    """

    def __init__(self):
        self.enabled = False
        self.current_position: Optional[Dict[str, int]] = None
        self.current_map: Optional[str] = None
        self.current_map_key: Optional[str] = None
        self.current_facing: Optional[str] = None
        self.game_state_type: Optional[str] = None
        self.total_decisions: int = 0
        self.session_id: Optional[str] = None
        self.agent_strategy: Optional[str] = None
        self.recent_decisions: List[Dict[str, Any]] = []
        self.last_outcome: Optional[Dict[str, Any]] = None
        self.map_summary: Optional[str] = None
        self.map_connections_count: int = 0

    def update(
        self,
        position: Dict[str, int],
        map_name: str,
        map_key: str,
        facing: str,
        game_state_type: str,
        total_decisions: int,
        decision: Dict[str, Any],
        outcome: Dict[str, Any],
        map_summary: str,
        map_connections_count: int = 0
    ):
        """Update state from the main loop"""
        self.enabled = True
        self.current_position = position
        self.current_map = map_name
        self.current_map_key = map_key
        self.current_facing = facing
        self.game_state_type = game_state_type
        self.total_decisions = total_decisions
        self.last_outcome = outcome

        # Keep last 20 decisions in memory for HTTP display
        self.recent_decisions.append({
            "number": total_decisions,
            "action": decision.get("action"),
            "reasoning": decision.get("reasoning"),
            "outcome_type": outcome.get("type"),
            "outcome_success": outcome.get("success"),
            "position": position,
            "map": map_name,
            "facing": facing
        })
        if len(self.recent_decisions) > 20:
            self.recent_decisions = self.recent_decisions[-20:]

        self.map_summary = map_summary
        self.map_connections_count = map_connections_count

    def to_dict(self) -> Dict[str, Any]:
        """Serialize full state for HTTP response"""
        return {
            "enabled": self.enabled,
            "position": self.current_position,
            "map": self.current_map,
            "map_key": self.current_map_key,
            "facing": self.current_facing,
            "game_state_type": self.game_state_type,
            "total_decisions": self.total_decisions,
            "session_id": self.session_id,
            "agent_strategy": self.agent_strategy,
            "last_outcome": self.last_outcome,
            "map_summary": self.map_summary,
            "map_connections_count": self.map_connections_count
        }


# Global singleton accessed by both trainer and HTTP server
llm_state = LLMState()
