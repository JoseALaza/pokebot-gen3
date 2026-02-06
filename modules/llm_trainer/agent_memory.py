"""Agent Memory - Hierarchical goal and memory system for persistent agent behavior"""

import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
from collections import deque


class AgentMemory:
    """
    Manages hierarchical goals and persistent memory for the LLM agent.

    Goal Hierarchy:
    - Long-term: Overall game objective (e.g., "Beat the Elite Four")
    - Medium-term: Current major objective (e.g., "Get first Pokemon and leave Pallet Town")
    - Short-term: Immediate task (e.g., "Exit this building", "Talk to NPC")

    Memory Types:
    - Observations: Facts learned about the world
    - Plans: Current strategy/approach
    - Spatial: Known locations of important things
    """

    def __init__(self, save_path: Optional[Path] = None):
        self.save_path = save_path

        # Goal hierarchy
        self.long_term_goal = "Progress through the Pokemon FireRed story"
        self.medium_term_goal = ""
        self.short_term_goal = ""
        self.short_term_goal_age = 0

        # Memory storage
        self.observations: List[str] = []  # Things we've learned
        self.current_plan: str = ""  # Current strategy
        self.spatial_memory: Dict[str, Any] = {}  # map_key -> {notes, important_tiles}

        # Recent history for context (last N events)
        self.recent_events: deque = deque(maxlen=10)

        # Exploration tracking
        self.visited_tiles: Dict[str, set] = {}  # map_key -> set of (x, y) tuples
        self.stuck_counter = 0  # How many times we've been in same area
        self.last_positions: deque = deque(maxlen=20)  # Track recent positions

        # Load existing memory if available
        if save_path:
            self._load()

    def set_long_term_goal(self, goal: str):
        """Set the overarching game objective"""
        self.long_term_goal = goal
        self._save()

    def set_medium_term_goal(self, goal: str):
        """Set current major objective"""
        if goal != self.medium_term_goal:
            self.medium_term_goal = goal
            self.add_event(f"New objective: {goal}")
            self._save()

    def set_short_term_goal(self, goal: str):
        """Set immediate task"""
        if goal != self.short_term_goal:
            self.short_term_goal = goal
            self.short_term_goal_age = 0
            self._save()

    def clear_short_term_goal(self):
        """Clear short-term goal when completed"""
        if self.short_term_goal:
            self.add_event(f"Completed: {self.short_term_goal}")
            self.short_term_goal = ""
            self.short_term_goal_age = 0
            self._save()

    def add_observation(self, observation: str):
        """Add a learned fact about the world"""
        if observation not in self.observations:
            self.observations.append(observation)
            # Keep only last 20 observations
            if len(self.observations) > 20:
                self.observations = self.observations[-20:]
            self._save()

    def set_plan(self, plan: str):
        """Set the current strategy/approach"""
        self.current_plan = plan
        self._save()

    def add_event(self, event: str):
        """Add a significant event to recent history"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.recent_events.append(f"[{timestamp}] {event}")

    def add_spatial_note(self, map_key: str, note: str):
        """Add a note about a specific map"""
        if map_key not in self.spatial_memory:
            self.spatial_memory[map_key] = {"notes": [], "important_tiles": []}
        if note not in self.spatial_memory[map_key]["notes"]:
            self.spatial_memory[map_key]["notes"].append(note)
            self._save()

    def mark_important_tile(self, map_key: str, x: int, y: int, description: str):
        """Mark a tile as important (door, NPC, item, etc.)"""
        if map_key not in self.spatial_memory:
            self.spatial_memory[map_key] = {"notes": [], "important_tiles": []}

        tile_info = {"x": x, "y": y, "description": description}
        # Don't add duplicates
        for existing in self.spatial_memory[map_key]["important_tiles"]:
            if existing["x"] == x and existing["y"] == y:
                existing["description"] = description  # Update description
                return

        self.spatial_memory[map_key]["important_tiles"].append(tile_info)
        self._save()

    def record_position(self, map_key: str, x: int, y: int):
        """Record current position for stuck detection"""
        pos = (map_key, x, y)
        self.last_positions.append(pos)
        if self.short_term_goal:
            self.short_term_goal_age += 1

        # Track visited tiles per map
        if map_key not in self.visited_tiles:
            self.visited_tiles[map_key] = set()
        self.visited_tiles[map_key].add((x, y))

        # Detect if stuck (same small area repeatedly)
        if len(self.last_positions) >= 10:
            recent = list(self.last_positions)[-10:]
            unique_positions = set(recent)
            if len(unique_positions) <= 3:
                self.stuck_counter += 1
            else:
                self.stuck_counter = max(0, self.stuck_counter - 1)

    def is_stuck(self) -> bool:
        """Check if agent seems to be stuck in a loop"""
        return self.stuck_counter >= 3

    def get_exploration_priority(self, map_key: str, traversal_map: List[List[str]]) -> Dict[str, Any]:
        """
        Analyze the traversal map and suggest exploration priorities.

        Returns:
            Dict with:
            - unexplored_directions: which directions have unknown tiles
            - nearest_transition: closest T tile if any
            - suggested_direction: recommended direction to explore
        """
        if not traversal_map:
            return {"unexplored_directions": [], "nearest_transition": None, "suggested_direction": None}

        # Find player position (P) in the map
        player_y, player_x = None, None
        for y, row in enumerate(traversal_map):
            for x, cell in enumerate(row):
                if cell == 'P':
                    player_y, player_x = y, x
                    break
            if player_y is not None:
                break

        if player_y is None:
            return {"unexplored_directions": [], "nearest_transition": None, "suggested_direction": None}

        # Check each direction for unknowns and transitions
        directions = {
            "Up": (-1, 0),
            "Down": (1, 0),
            "Left": (0, -1),
            "Right": (0, 1)
        }

        unexplored = []
        transitions = []
        walkable = []

        for dir_name, (dy, dx) in directions.items():
            ny, nx = player_y + dy, player_x + dx
            if 0 <= ny < len(traversal_map) and 0 <= nx < len(traversal_map[0]):
                cell = traversal_map[ny][nx]
                if cell == '?':
                    unexplored.append(dir_name)
                elif cell == 'T':
                    transitions.append({"direction": dir_name, "distance": 1})
                elif cell == 'W':
                    walkable.append(dir_name)

        # Look further for transitions and unexplored areas
        for distance in range(2, 5):
            for dir_name, (dy, dx) in directions.items():
                ny, nx = player_y + (dy * distance), player_x + (dx * distance)
                if 0 <= ny < len(traversal_map) and 0 <= nx < len(traversal_map[0]):
                    cell = traversal_map[ny][nx]
                    if cell == 'T' and not any(t["direction"] == dir_name for t in transitions):
                        transitions.append({"direction": dir_name, "distance": distance})
                    elif cell == '?' and dir_name not in unexplored:
                        unexplored.append(dir_name)

        # Suggest direction based on priority:
        # 1. Unexplored areas (if not stuck)
        # 2. Transitions (to progress)
        # 3. Walkable areas we haven't visited much
        suggested = None
        if unexplored and not self.is_stuck():
            suggested = unexplored[0]
        elif transitions:
            suggested = transitions[0]["direction"]
        elif walkable:
            suggested = walkable[0]

        return {
            "unexplored_directions": unexplored,
            "transitions": transitions,
            "walkable_directions": walkable,
            "suggested_direction": suggested,
            "is_stuck": self.is_stuck()
        }

    def get_context_for_prompt(self, map_key: str = "") -> str:
        """Generate context string for LLM prompt"""
        lines = []

        # Goals
        lines.append("## Current Goals")
        lines.append(f"- Long-term: {self.long_term_goal}")
        if self.medium_term_goal:
            lines.append(f"- Current objective: {self.medium_term_goal}")
        if self.short_term_goal:
            lines.append(f"- Immediate task: {self.short_term_goal}")

        # Current plan
        if self.current_plan:
            lines.append(f"\n## Current Plan")
            lines.append(self.current_plan)

        # Spatial memory for current map
        if map_key and map_key in self.spatial_memory:
            mem = self.spatial_memory[map_key]
            if mem["notes"] or mem["important_tiles"]:
                lines.append(f"\n## Known Info About This Area")
                for note in mem["notes"][-5:]:
                    lines.append(f"- {note}")
                for tile in mem["important_tiles"][-5:]:
                    lines.append(f"- ({tile['x']}, {tile['y']}): {tile['description']}")

        # Recent events
        if self.recent_events:
            lines.append(f"\n## Recent Events")
            for event in list(self.recent_events)[-5:]:
                lines.append(f"- {event}")

        # Stuck warning
        if self.is_stuck():
            lines.append("\n## ⚠️ WARNING: You seem to be stuck in a loop!")
            lines.append("Try a DIFFERENT approach - go to unexplored areas or use a transition (T tile)")
        if self.short_term_goal and self.short_term_goal_age >= 40:
            lines.append("\n## ⚠️ Goal Staleness Warning")
            lines.append("Your immediate task seems to be taking too long. Consider updating the goal or changing the plan.")

        return "\n".join(lines)

    def parse_llm_memory_updates(self, response: Dict[str, Any]):
        """
        Parse LLM response for memory/goal updates.

        Expected format in response:
        {
            "action": "...",
            "reasoning": "...",
            "goal_update": "new short-term goal" (optional),
            "observation": "something I learned" (optional),
            "plan": "my current strategy" (optional)
        }
        """
        if "goal_update" in response and response["goal_update"]:
            goal_update = response["goal_update"]
            if isinstance(goal_update, dict):
                short_term = goal_update.get("short_term")
                medium_term = goal_update.get("medium_term")
                long_term = goal_update.get("long_term")
                if long_term:
                    self.set_long_term_goal(long_term)
                if medium_term:
                    self.set_medium_term_goal(medium_term)
                if short_term:
                    self.set_short_term_goal(short_term)
            else:
                self.set_short_term_goal(goal_update)

        if "observation" in response and response["observation"]:
            self.add_observation(response["observation"])

        if "plan" in response and response["plan"]:
            self.set_plan(response["plan"])

    def _save(self):
        """Save memory to disk"""
        if not self.save_path:
            return

        data = {
            "long_term_goal": self.long_term_goal,
            "medium_term_goal": self.medium_term_goal,
            "short_term_goal": self.short_term_goal,
            "short_term_goal_age": self.short_term_goal_age,
            "observations": self.observations,
            "current_plan": self.current_plan,
            "spatial_memory": self.spatial_memory,
            "recent_events": list(self.recent_events)
        }

        try:
            self.save_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.save_path, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            pass  # Silently fail on save errors

    def _load(self):
        """Load memory from disk"""
        if not self.save_path or not self.save_path.exists():
            return

        try:
            with open(self.save_path, 'r') as f:
                data = json.load(f)

            self.long_term_goal = data.get("long_term_goal", self.long_term_goal)
            self.medium_term_goal = data.get("medium_term_goal", "")
            self.short_term_goal = data.get("short_term_goal", "")
            self.short_term_goal_age = data.get("short_term_goal_age", 0)
            self.observations = data.get("observations", [])
            self.current_plan = data.get("current_plan", "")
            self.spatial_memory = data.get("spatial_memory", {})
            self.recent_events = deque(data.get("recent_events", []), maxlen=10)
        except Exception as e:
            pass  # Silently fail on load errors
