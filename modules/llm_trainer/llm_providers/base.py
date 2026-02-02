"""Base LLM Provider - Abstract interface for all LLM providers"""

import json
import re
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from textwrap import dedent


# System prompt for Pokemon gameplay
POKEMON_SYSTEM_PROMPT = dedent("""
    You are playing Pokemon FireRed. You control a character in the overworld.

    You receive:
    - Player position (x, y), facing direction, current map
    - A tile map showing what's around you (9x15 grid, you're at center)
    - A traversal map showing where you can/can't walk (W=walkable, N=blocked, ?=unknown, P=you, T=transition, L=ledge)
    - Your Pokemon party info
    - Recent decision history

    You must respond with EXACTLY one JSON object:
    {
        "action": "Up|Down|Left|Right|A|B|WAIT",
        "reasoning": "Brief explanation of why"
    }

    Rules:
    - Choose one action per turn
    - Explore unknown areas (? tiles) to map them
    - Avoid repeatedly hitting walls (N tiles)
    - Use A to interact with NPCs, signs, doors
    - Use transitions (T tiles) to move between maps
    - Your goal is to progress through the game: explore, battle, collect badges
    - Be strategic about movement - don't wander randomly
""").strip()


def build_user_prompt(
    game_state: Dict[str, Any],
    vision_data: Dict[str, Any],
    recent_decisions: List[Dict[str, Any]],
    map_summary: Optional[str] = None
) -> str:
    """Build the user prompt with current game context."""
    player = game_state.get("player", {})
    pos = player.get("position", {})
    party = game_state.get("party", [])

    # Format tile map as compact grid
    tile_map = vision_data.get("tile_map", [])
    tile_str = ""
    if tile_map:
        for row in tile_map:
            tile_str += " ".join(t[:4].ljust(4) for t in row) + "\n"

    # Format recent decisions
    history = ""
    for d in recent_decisions[-5:]:
        history += f"  #{d.get('decision_number', '?')}: {d.get('action', '?')} -> {d.get('reasoning', '')}\n"

    # Format party
    party_str = ""
    for p in party[:3]:
        party_str += f"  {p.get('species', '?')} Lv{p.get('level', '?')} HP:{p.get('hp', {}).get('current', '?')}/{p.get('hp', {}).get('max', '?')}\n"

    return dedent(f"""
        Current State:
        - Position: ({pos.get('x', '?')}, {pos.get('y', '?')})
        - Facing: {player.get('facing', '?')}
        - Map: {player.get('map', '?')}
        {f'- Map Info: {map_summary}' if map_summary else ''}

        Party:
        {party_str or '  (none)'}

        Tile Map (you are at center):
        {tile_str or '  (no vision data)'}

        Recent Decisions:
        {history or '  (none)'}

        Choose your next action. Respond with JSON only.
    """).strip()


def parse_llm_response(response_text: str) -> Dict[str, Any]:
    """
    Parse LLM response text into a decision dict.
    Handles JSON embedded in markdown code blocks or plain text.
    """
    # Try to extract JSON from code blocks
    code_block = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
    if code_block:
        response_text = code_block.group(1)

    # Try to find JSON object
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

            return {
                "action": action,
                "reasoning": reasoning,
                "confidence": 0.8,
                "strategy": "llm"
            }
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
        map_summary: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Make a gameplay decision using the LLM.

        Args:
            game_state: Current game state
            vision_data: Vision processor output
            recent_decisions: Recent decision history
            map_summary: Current map summary string

        Returns:
            Decision dict with action and reasoning
        """
        user_prompt = build_user_prompt(
            game_state,
            vision_data,
            recent_decisions or [],
            map_summary
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
