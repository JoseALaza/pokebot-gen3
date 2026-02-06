"""Base LLM Provider - Abstract interface for all LLM providers"""

import json
import re
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from textwrap import dedent


# Comprehensive system prompt for Pokemon gameplay
POKEMON_SYSTEM_PROMPT = dedent("""
    You are an AI playing Pokemon FireRed. You control a trainer in the overworld.

    ## Game Mechanics
    - Movement: Up/Down/Left/Right moves one tile in that direction
    - In Pokemon, pressing a direction when NOT facing it will TURN you first (no movement)
    - Press the same direction again to actually MOVE after turning
    - A button: Interact with NPCs, read signs, pick up items, confirm dialogues
    - B button: Cancel, exit menus, speed up text
    - Ledges (L): Can only jump DOWN ledges, not up/sideways

    ## Map Information You Receive
    1. **Traversal Map**: Shows movement possibilities:
       - W = Walkable (confirmed you can walk here)
       - N = Blocked (confirmed obstacle - wall, object, NPC)
       - ? = Unknown (not yet explored)
       - P = Your current position
       - T = Transition (door, stairs, cave entrance - leads to another map)
       - I = Interactable (NPC, sign, or object you can interact with using A)
       - L = Ledge (can jump down only)

    ## Decision History
    You'll see your recent decisions with their OUTCOMES:
    - ✓ = Success (moved, interacted, etc.)
    - ✗ = Failed (blocked, couldn't move)
    - ⟳ = Turned (faced new direction but didn't move yet)

    ## Your Response Format
    Respond with a JSON object. Required fields:
    {
        "action": "Up|Down|Left|Right|A|B|WAIT",
        "reasoning": "Why this action advances your goal"
    }

    Optional fields to update your memory:
    {
        "goal_update": {
            "short_term": "Immediate task (if current one is done/changed)",
            "medium_term": "Current major objective (optional)",
            "long_term": "Overall objective (optional)"
        },
        "observation": "Important fact you learned (door location, NPC info, etc.)",
        "plan": "Your current strategy for achieving your goal"
    }

    ## CRITICAL STRATEGY - MAINTAIN FOCUS
    - You have GOALS shown below - every action should work toward them!
    - If you have a short-term goal, focus on it until complete
    - DON'T wander randomly - have a PURPOSE for each move
    - When you complete a goal, set a new one with "goal_update"
    - Use "observation" to remember important locations
    - If stuck, set a new plan with "plan"

    ## Exploration Priority
    1. First: Complete your current immediate goal
    2. Then: Use transition tiles (T) to explore new areas
    3. Then: Explore unknown tiles (?) to map the area
    4. Avoid: Revisiting the same tiles repeatedly
""").strip()


def build_user_prompt(
    game_state: Dict[str, Any],
    vision_data: Dict[str, Any],
    recent_decisions: List[Dict[str, Any]],
    map_summary: Optional[str] = None,
    traversal_context: Optional[Dict[str, Any]] = None,
    memory_context: Optional[str] = None,
    exploration_priority: Optional[Dict[str, Any]] = None
) -> str:
    """
    Build comprehensive user prompt with full game context.

    Args:
        game_state: Current game state from MemoryReader
        vision_data: Vision data including tile_map and traversal_map
        recent_decisions: Recent decisions WITH outcomes
        map_summary: Current map exploration summary
        traversal_context: Additional context about surroundings
        memory_context: Agent's goals, observations, and plans
        exploration_priority: Suggested directions and priorities
    """
    player = game_state.get("player", {})
    pos = player.get("position", {})
    facing = player.get("facing", "Down")
    party = game_state.get("party", [])

    # Build position and state section
    state_lines = [
        f"Position: ({pos.get('x', '?')}, {pos.get('y', '?')})",
        f"Facing: {facing}",
        f"Map: {player.get('map', '?')}",
    ]
    if map_summary:
        state_lines.append(f"Exploration: {map_summary}")

    # Format traversal map (shows W/N/?/P/T/I/L markers)
    traversal_map = vision_data.get("traversal_map", [])
    traversal_str = ""
    if traversal_map:
        for row in traversal_map:
            traversal_str += " ".join(row) + "\n"

    # Format tile map (shows terrain types) - more compact
    tile_map = vision_data.get("tile_map", [])
    tile_str = ""
    if tile_map:
        for row in tile_map:
            # Abbreviate tile names to 3 chars for readability
            tile_str += " ".join(t[:3].ljust(3) for t in row) + "\n"

    # Analyze what's in each direction from player position
    direction_info = _analyze_directions(traversal_map, tile_map, facing)

    # Format recent decisions WITH outcomes
    history = ""
    for d in recent_decisions[-8:]:  # Show last 8 decisions
        num = d.get('decision_number', '?')
        action = d.get('action', '?')
        outcome = d.get('outcome', {})

        # Determine outcome symbol
        if outcome.get('type') == 'blocked':
            symbol = "✗"
            result = "BLOCKED"
        elif outcome.get('type') == 'turn':
            symbol = "⟳"
            result = f"turned to face {action}"
        elif outcome.get('type') == 'movement':
            symbol = "✓"
            result = outcome.get('reason', 'moved')[:40]
        elif outcome.get('type') == 'map_change':
            symbol = "✓"
            result = "entered new area"
        elif outcome.get('type') == 'interaction':
            symbol = "✓"
            result = "triggered dialogue (A press)"
        elif outcome.get('type') == 'auto_dialogue':
            symbol = "💬"
            result = "stepped on trigger - auto dialogue!"
        elif outcome.get('success', True):
            symbol = "✓"
            result = outcome.get('reason', 'ok')[:40]
        else:
            symbol = "?"
            result = outcome.get('reason', '')[:40]

        reasoning = d.get('reasoning', '')[:50]
        history += f"  {symbol} #{num}: {action:5} | {result}\n"

    # Format party (brief)
    party_str = ""
    for i, p in enumerate(party[:6]):
        species = p.get('species', '?')
        level = p.get('level', '?')
        hp = p.get('hp', {})
        hp_cur = hp.get('current', '?')
        hp_max = hp.get('max', '?')
        party_str += f"  {i+1}. {species} Lv{level} ({hp_cur}/{hp_max} HP)\n"

    # Build known connections info
    connections_str = ""
    if traversal_context and traversal_context.get('connections'):
        connections_str = "\n## Known Exits\n"
        for conn in traversal_context['connections'][:5]:
            connections_str += f"  - {conn.get('direction', '?')}: leads to {conn.get('target_map', '?')}\n"

    # Build exploration suggestions
    explore_str = ""
    if exploration_priority:
        explore_str = "\n## Exploration Suggestions\n"
        if exploration_priority.get('is_stuck'):
            explore_str += "⚠️ WARNING: You seem to be going in circles!\n"
        if exploration_priority.get('suggested_direction'):
            explore_str += f"- Suggested direction: {exploration_priority['suggested_direction']}\n"
        if exploration_priority.get('unexplored_directions'):
            explore_str += f"- Unexplored areas: {', '.join(exploration_priority['unexplored_directions'])}\n"
        if exploration_priority.get('transitions'):
            for t in exploration_priority['transitions'][:2]:
                explore_str += f"- Transition {t['direction']} ({t['distance']} tiles away)\n"

    # Build the full prompt - put goals/memory FIRST so LLM sees them
    default_goals = (
        "## Current Goals\n"
        "- Long-term: Progress through the Pokemon FireRed story\n"
        "- Current objective: Locate the next exit or NPC that advances the story\n"
        "- Immediate task: Use the traversal map to reach a transition (T) or interactable (I)\n"
    )
    prompt = f"""{memory_context if memory_context else default_goals}

## Current State
{chr(10).join('- ' + line for line in state_lines)}

## What's Around You
{direction_info}
{explore_str}
## Traversal Map (P=you, W=walkable, N=blocked, ?=unknown, T=transition, I=interact)
{traversal_str.strip() if traversal_str else '(no traversal data)'}

## Your Pokemon
{party_str.strip() if party_str else '(no pokemon yet)'}

## Recent Actions & Results
{history.strip() if history else '(first decision)'}
{connections_str}
## Your Turn
Choose an action that advances your goals. If you complete a goal, set a new one.
Respond with JSON: {{"action": "...", "reasoning": "...", "goal_update": {{"short_term": "...", "medium_term": "...", "long_term": "..."}} (optional)}}"""

    return prompt


def _analyze_directions(traversal_map: List[List[str]], tile_map: List[List[str]], facing: str) -> str:
    """Analyze what's in each cardinal direction from player."""
    if not traversal_map:
        return "(no map data)"

    # Find player position (P) in traversal map
    player_y, player_x = None, None
    for y, row in enumerate(traversal_map):
        for x, cell in enumerate(row):
            if cell == 'P':
                player_y, player_x = y, x
                break
        if player_y is not None:
            break

    if player_y is None:
        return "(player position not found)"

    directions = {
        "Up": (player_y - 1, player_x),
        "Down": (player_y + 1, player_x),
        "Left": (player_y, player_x - 1),
        "Right": (player_y, player_x + 1)
    }

    marker_meanings = {
        'W': 'walkable',
        'N': 'BLOCKED',
        '?': 'unknown',
        'T': 'TRANSITION (exit/door)',
        'I': 'interactable',
        'L': 'ledge'
    }

    result_lines = []
    for dir_name, (y, x) in directions.items():
        # Check bounds
        if 0 <= y < len(traversal_map) and 0 <= x < len(traversal_map[0]):
            marker = traversal_map[y][x]
            meaning = marker_meanings.get(marker, marker)

            # Get tile type if available
            tile_type = ""
            if tile_map and 0 <= y < len(tile_map) and 0 <= x < len(tile_map[0]):
                tile_type = f" ({tile_map[y][x]})"

            # Mark if this is the direction we're facing
            facing_marker = " ← facing" if dir_name == facing else ""
            result_lines.append(f"- {dir_name}: {meaning}{tile_type}{facing_marker}")
        else:
            result_lines.append(f"- {dir_name}: out of bounds")

    return "\n".join(result_lines)


def parse_llm_response(response_text: str) -> Dict[str, Any]:
    """
    Parse LLM response text into a decision dict.
    Handles JSON embedded in markdown code blocks or plain text.
    Also extracts optional memory updates (goal_update, observation, plan).
    """
    # Try to extract JSON from code blocks
    code_block = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
    if code_block:
        response_text = code_block.group(1)

    # Try to find JSON object - allow for nested content
    json_match = re.search(r'\{[^{}]*"action"[^{}]*\}', response_text, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group())
            action = data.get("action", "WAIT")
            reasoning = data.get("reasoning", "")

            # Normalize action
            valid_actions = ["Up", "Down", "Left", "Right", "A", "B", "Start", "Select", "WAIT"]
            action_map = {a.lower(): a for a in valid_actions}
            action = action_map.get(action.lower(), "WAIT")

            result = {
                "action": action,
                "reasoning": reasoning,
                "confidence": 0.8,
                "strategy": "llm"
            }

            # Extract optional memory updates
            if "goal_update" in data and data["goal_update"]:
                result["goal_update"] = data["goal_update"]
            if "observation" in data and data["observation"]:
                result["observation"] = data["observation"]
            if "plan" in data and data["plan"]:
                result["plan"] = data["plan"]

            return result
        except json.JSONDecodeError:
            pass

    # Fallback: try to find a direction keyword
    for direction in ["Up", "Down", "Left", "Right"]:
        if direction.lower() in response_text.lower():
            return {
                "action": direction,
                "reasoning": f"Parsed from response: {response_text[:100]}",
                "confidence": 0.3,
                "strategy": "llm_fallback"
            }

    return {
        "action": "WAIT",
        "reasoning": f"Could not parse LLM response: {response_text[:100]}",
        "confidence": 0.1,
        "strategy": "llm_fallback"
    }


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers."""

    def __init__(self, model: str, api_key: Optional[str] = None):
        self.model = model
        self.api_key = api_key
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_requests = 0
        self.total_errors = 0

    @abstractmethod
    def _call_api(self, system_prompt: str, user_prompt: str) -> str:
        """
        Make the actual API call. Must be implemented by subclasses.

        Args:
            system_prompt: System/instruction prompt
            user_prompt: User message with game context

        Returns:
            Raw response text from the LLM
        """
        pass

    def decide(
        self,
        game_state: Dict[str, Any],
        vision_data: Dict[str, Any],
        recent_decisions: Optional[List[Dict[str, Any]]] = None,
        map_summary: Optional[str] = None,
        traversal_context: Optional[Dict[str, Any]] = None,
        memory_context: Optional[str] = None,
        exploration_priority: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Make a gameplay decision using the LLM.

        Args:
            game_state: Current game state
            vision_data: Vision processor output (should include traversal_map)
            recent_decisions: Recent decision history WITH outcomes
            map_summary: Current map summary string
            traversal_context: Additional context (connections, etc.)
            memory_context: Agent's goals, observations, plans
            exploration_priority: Suggested directions and stuck detection

        Returns:
            Decision dict with action and reasoning
        """
        user_prompt = build_user_prompt(
            game_state,
            vision_data,
            recent_decisions or [],
            map_summary,
            traversal_context,
            memory_context,
            exploration_priority
        )

        try:
            response_text = self._call_api(POKEMON_SYSTEM_PROMPT, user_prompt)
            self.total_requests += 1
            decision = parse_llm_response(response_text)
            decision["raw_response"] = response_text[:500]
            return decision
        except Exception as e:
            self.total_errors += 1
            return {
                "action": "WAIT",
                "reasoning": f"LLM error: {str(e)[:100]}",
                "confidence": 0.0,
                "strategy": "llm_error"
            }

    def get_usage_stats(self) -> Dict[str, Any]:
        """Get token usage and cost statistics."""
        return {
            "provider": self.__class__.__name__,
            "model": self.model,
            "total_requests": self.total_requests,
            "total_errors": self.total_errors,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens
        }
