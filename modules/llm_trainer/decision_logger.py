"""Decision Logger - Logs all decisions to JSON files for analysis"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional


class DecisionLogger:
    """
    Logs all agent decisions to JSON files for debugging and training.

    Each session gets its own directory with:
    - metadata.json: Session info (start time, strategy, total decisions)
    - decision_NNNN.json: Individual decision logs with full context
    """

    MAX_SESSIONS = 20  # Keep last N sessions, clean up older ones

    def __init__(self, profile_path: Path):
        self.sessions_dir = profile_path / "llm_trainer" / "sessions"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

        # Start new session
        self.session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.session_dir = self.sessions_dir / self.session_id
        self.session_dir.mkdir()

        self.metadata: Dict[str, Any] = {
            "session_id": self.session_id,
            "start_time": datetime.now().isoformat(),
            "end_time": None,
            "total_decisions": 0,
            "start_map": None,
            "start_position": None,
            "agent_strategy": None,
            "llm_provider": None
        }

        self._save_metadata()
        self._cleanup_old_sessions()

    def _save_metadata(self):
        """Save session metadata"""
        try:
            with open(self.session_dir / "metadata.json", 'w') as f:
                json.dump(self.metadata, f, indent=2)
        except Exception:
            pass

    def _cleanup_old_sessions(self):
        """Remove oldest sessions if over MAX_SESSIONS"""
        try:
            sessions = sorted(
                [d for d in self.sessions_dir.iterdir() if d.is_dir()],
                key=lambda d: d.name
            )
            while len(sessions) > self.MAX_SESSIONS:
                oldest = sessions.pop(0)
                for f in oldest.iterdir():
                    f.unlink()
                oldest.rmdir()
        except Exception:
            pass

    def set_session_info(
        self,
        start_map: Optional[str] = None,
        start_position: Optional[List[int]] = None,
        agent_strategy: Optional[str] = None,
        llm_provider: Optional[str] = None
    ):
        """Set session metadata after initialization"""
        if start_map is not None:
            self.metadata["start_map"] = start_map
        if start_position is not None:
            self.metadata["start_position"] = start_position
        if agent_strategy is not None:
            self.metadata["agent_strategy"] = agent_strategy
        if llm_provider is not None:
            self.metadata["llm_provider"] = llm_provider
        self._save_metadata()

    def log_decision(
        self,
        decision_number: int,
        frame: int,
        game_state_before: Dict[str, Any],
        vision_data: Dict[str, Any],
        decision: Dict[str, Any],
        execution_success: bool,
        outcome: Dict[str, Any],
        game_state_after: Optional[Dict[str, Any]] = None
    ):
        """
        Log a single decision with full context.

        Args:
            decision_number: Sequential decision number
            frame: Current frame count
            game_state_before: Game state before action
            vision_data: Vision processor output
            decision: Agent's decision
            execution_success: Whether action executed
            outcome: Outcome of the action
            game_state_after: Game state after action (optional)
        """
        entry = {
            "decision_number": decision_number,
            "timestamp": datetime.now().isoformat(),
            "frame": frame,
            "game_state_before": game_state_before,
            "vision_data": {
                "tile_map": vision_data.get("tile_map"),
                "tiles_x": vision_data.get("tiles_x"),
                "tiles_y": vision_data.get("tiles_y")
            },
            "decision": decision,
            "execution": {
                "success": execution_success
            },
            "outcome": outcome
        }

        if game_state_after is not None:
            entry["game_state_after"] = game_state_after

        # Save to file
        filename = f"decision_{decision_number:04d}.json"
        try:
            with open(self.session_dir / filename, 'w') as f:
                json.dump(entry, f, indent=2)
        except Exception:
            pass

        # Update metadata
        self.metadata["total_decisions"] = decision_number
        self._save_metadata()

    def end_session(self):
        """Mark session as ended"""
        self.metadata["end_time"] = datetime.now().isoformat()
        self._save_metadata()

    def get_recent_decisions(self, count: int = 10) -> List[Dict[str, Any]]:
        """
        Load the N most recent decisions from disk.

        Args:
            count: Number of recent decisions to load

        Returns:
            List of decision entries
        """
        decisions = []
        try:
            files = sorted(self.session_dir.glob("decision_*.json"), reverse=True)
            for f in files[:count]:
                with open(f, 'r') as fh:
                    decisions.append(json.load(fh))
        except Exception:
            pass
        decisions.reverse()
        return decisions
