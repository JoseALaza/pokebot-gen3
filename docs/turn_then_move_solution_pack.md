# Turn-Then-Move Solution Pack

# Solution 1: Agent-Level Turn Completion Guard
**Category:** Hybrid

## Overview
This solution introduces a deterministic post-turn controller in `Agent` that tracks a `pending_turn_direction` whenever the last outcome was `type == "turn"`, then enforces one immediate retry of the same direction on the next decision unless a guard condition cancels it. Prompt updates still teach the LLM, but correctness no longer depends on provider compliance. The override is narrow (single-step, directional-only), so it reduces spinning while keeping the LLM in control for normal navigation.

## Why This Solves Spinning
- A turn outcome explicitly sets a one-step obligation: "repeat same direction once."
- On the next decision, if LLM changes direction, `Agent` rewrites action to the pending direction and tags the decision (`turn_completion_forced=true`).
- If the follow-up is blocked, pending state is cleared so you avoid repeated false forcing.
- If dialogue/menu/battle state is detected, pending state is canceled.
- Works across providers because enforcement is in Python control flow, not model-specific instruction following.

## Complete Implementation

### File: `modules/llm_trainer/agent.py`
```python
"""Agent - Makes decisions based on game state and vision"""

import random
from typing import Dict, Any, Optional, List
from datetime import datetime
from modules.console import console


class MockLLM:
    """
    Mock LLM for testing without API calls.

    Implements simple strategies:
    - random: Random walk
    - scripted_exit_house: Hardcoded sequence to exit player's house
    - scripted: Custom action list (set via set_script())
    - explore: Basic exploration (stay in motion, avoid getting stuck)
    """

    STRATEGIES = ["random", "scripted_exit_house", "scripted", "explore"]

    # What to do when a scripted list is exhausted
    SCRIPT_END_STOP = "stop"       # WAIT forever
    SCRIPT_END_LOOP = "loop"       # Restart from beginning
    SCRIPT_END_EXPLORE = "explore"  # Switch to explore strategy

    def __init__(self, strategy: str = "random"):
        if strategy not in self.STRATEGIES:
            raise ValueError(f"Unknown strategy: {strategy}. Valid: {self.STRATEGIES}")

        self.strategy = strategy
        self.step_count = 0

        # Scripted sequence for exiting player's house in FireRed
        self.exit_house_sequence = [
            "Down", "Down", "Down", "Down", "Down"
        ]
        self.sequence_index = 0

        # Custom scripted sequence
        self.script: List[str] = []
        self.script_index = 0
        self.script_on_end: str = self.SCRIPT_END_STOP

        console.print(f"[yellow]Mock LLM initialized with strategy: {strategy}[/]")

    def set_script(self, actions: List[str], on_end: str = "stop"):
        self.script = actions
        self.script_index = 0
        self.script_on_end = on_end
        self.strategy = "scripted"
        console.print(f"[yellow]Script loaded: {len(actions)} actions, on_end={on_end}[/]")
        console.print(f"[dim yellow]  Actions: {', '.join(actions[:20])}{'...' if len(actions) > 20 else ''}[/]")

    def decide(self, game_state: Dict[str, Any], vision_data: Dict[str, Any]) -> Dict[str, Any]:
        self.step_count += 1

        if self.strategy == "random":
            return self._random_walk(game_state, vision_data)
        elif self.strategy == "scripted_exit_house":
            return self._scripted_exit_house(game_state, vision_data)
        elif self.strategy == "scripted":
            return self._scripted(game_state, vision_data)
        elif self.strategy == "explore":
            return self._explore(game_state, vision_data)
        else:
            return self._random_walk(game_state, vision_data)

    def _random_walk(self, game_state: Dict[str, Any], vision_data: Dict[str, Any]) -> Dict[str, Any]:
        actions = ["Up", "Down", "Left", "Right", "A", "WAIT"]
        weights = [20, 20, 20, 20, 10, 10]

        action = random.choices(actions, weights=weights)[0]

        return {
            "action": action,
            "reasoning": f"Random walk strategy - step {self.step_count}, chose {action}",
            "confidence": 0.5,
            "strategy": "random",
            "step": self.step_count
        }

    def _scripted(self, game_state: Dict[str, Any], vision_data: Dict[str, Any]) -> Dict[str, Any]:
        if self.script_index >= len(self.script):
            if self.script_on_end == self.SCRIPT_END_LOOP:
                self.script_index = 0
                console.print("[yellow]Script looping from beginning[/]")
            elif self.script_on_end == self.SCRIPT_END_EXPLORE:
                console.print("[yellow]Script complete, switching to explore[/]")
                self.strategy = "explore"
                return self._explore(game_state, vision_data)
            else:
                return {
                    "action": "WAIT",
                    "reasoning": f"Script complete ({len(self.script)} actions executed)",
                    "confidence": 1.0,
                    "strategy": "scripted",
                    "step": self.step_count
                }

        action = self.script[self.script_index]
        self.script_index += 1

        return {
            "action": action,
            "reasoning": f"Script step {self.script_index}/{len(self.script)}: {action}",
            "confidence": 1.0,
            "strategy": "scripted",
            "step": self.step_count
        }

    def _scripted_exit_house(self, game_state: Dict[str, Any], vision_data: Dict[str, Any]) -> Dict[str, Any]:
        map_name = game_state['player']['map']
        in_house = "Player’s House" in map_name or "Players House" in map_name
        console.print(in_house, map_name)
        if not in_house:
            console.print(f"[bold green]Successfully exited house! Current map: {map_name}[/]")
            console.print("[bold green]Switching to explore mode.[/]")
            self.strategy = "explore"
            return self._explore(game_state, vision_data)

        if self.sequence_index >= len(self.exit_house_sequence):
            console.print(f"[yellow]Exit sequence complete but still in house ({map_name}). Retrying...[/]")
            self.sequence_index = 0

        action = self.exit_house_sequence[self.sequence_index]
        self.sequence_index += 1

        return {
            "action": action,
            "reasoning": f"Exiting house - step {self.sequence_index}/{len(self.exit_house_sequence)} (Map: {map_name})",
            "confidence": 1.0,
            "strategy": "scripted_exit_house",
            "step": self.step_count
        }

    def _explore(self, game_state: Dict[str, Any], vision_data: Dict[str, Any]) -> Dict[str, Any]:
        facing = game_state['player']['facing']

        choice = random.random()

        if choice < 0.6:
            action = facing
            reasoning = f"Continuing {facing}"
        elif choice < 0.9:
            directions = ["Up", "Down", "Left", "Right"]
            directions.remove(facing)
            action = random.choice(directions)
            reasoning = f"Changing direction from {facing} to {action}"
        else:
            action = random.choice(["A", "WAIT"])
            reasoning = f"Trying {action}"

        return {
            "action": action,
            "reasoning": reasoning,
            "confidence": 0.7,
            "strategy": "explore",
            "step": self.step_count
        }


class Agent:
    """Agent that makes decisions for the LLM Trainer."""

    DIRECTION_ACTIONS = {"Up", "Down", "Left", "Right"}

    def __init__(
        self,
        use_mock: bool = True,
        mock_strategy: str = "random",
        provider: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        memory_save_path: Optional[str] = None
    ):
        self.use_mock = use_mock
        self.provider = None
        self.provider_name = "mock"

        if use_mock:
            self.llm = MockLLM(strategy=mock_strategy)
            console.print(f"[yellow]Agent initialized with Mock LLM[/]")
        else:
            from modules.llm_trainer.llm_providers import create_provider
            kwargs = {}
            if model:
                kwargs["model"] = model
            if api_key:
                kwargs["api_key"] = api_key
            self.provider = create_provider(provider, **kwargs)
            self.provider_name = provider
            self.llm = None
            console.print(f"[yellow]Agent initialized with {provider} ({self.provider.model})[/]")

        self.decision_history = []
        self.total_decisions = 0

        from pathlib import Path
        from modules.llm_trainer.agent_memory import AgentMemory
        save_path = Path(memory_save_path) if memory_save_path else None
        self.memory = AgentMemory(save_path=save_path)
        console.print(f"[yellow]Agent memory initialized[/]")

        # Turn completion state
        self.pending_turn_direction: Optional[str] = None
        self.pending_turn_set_frame: int = 0
        self.turn_completion_overrides: int = 0

    def _is_interrupt_state(self, game_state: Dict[str, Any]) -> bool:
        # Keep lenient: only check known top-level flags if present.
        for key in ("in_battle", "in_dialogue", "in_menu"):
            if game_state.get(key) is True:
                return True
        return False

    def _apply_turn_completion_guard(
        self,
        decision: Dict[str, Any],
        game_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        if not self.pending_turn_direction:
            return decision

        if self._is_interrupt_state(game_state):
            self.pending_turn_direction = None
            return decision

        frame = game_state.get("frame", 0)
        if frame - self.pending_turn_set_frame > 180:
            self.pending_turn_direction = None
            return decision

        action = decision.get("action", "WAIT")
        if action in self.DIRECTION_ACTIONS and action != self.pending_turn_direction:
            original_action = action
            decision["action"] = self.pending_turn_direction
            decision["reasoning"] = (
                f"[AUTO] Completing turn->move sequence: {self.pending_turn_direction} "
                f"(LLM picked {original_action})"
            )
            decision["turn_completion_forced"] = True
            decision["forced_from_action"] = original_action
            self.turn_completion_overrides += 1
            console.print(
                f"[yellow]Turn completion override: {original_action} -> {self.pending_turn_direction}[/]"
            )

        # Clear after one attempt (forced or model-chosen)
        if decision.get("action") == self.pending_turn_direction:
            self.pending_turn_direction = None

        return decision

    def decide(
        self,
        game_state: Dict[str, Any],
        vision_data: Dict[str, Any],
        map_summary: Optional[str] = None,
        traversal_context: Optional[Dict[str, Any]] = None,
        map_key: Optional[str] = None
    ) -> Dict[str, Any]:
        pos = game_state.get("player", {}).get("position", {})
        if map_key and pos:
            self.memory.record_position(map_key, pos.get("x", 0), pos.get("y", 0))

        traversal_map = vision_data.get("traversal_map", [])
        exploration_priority = self.memory.get_exploration_priority(map_key or "", traversal_map)

        memory_context = self.memory.get_context_for_prompt(map_key or "")

        if self.use_mock:
            decision = self.llm.decide(game_state, vision_data)
        else:
            decision = self.provider.decide(
                game_state,
                vision_data,
                recent_decisions=self.decision_history[-10:],
                map_summary=map_summary,
                traversal_context=traversal_context,
                memory_context=memory_context,
                exploration_priority=exploration_priority
            )

        decision = self._apply_turn_completion_guard(decision, game_state)

        self.memory.parse_llm_memory_updates(decision)

        decision["timestamp"] = datetime.now().isoformat()
        decision["frame"] = game_state.get("frame", 0)
        decision["decision_number"] = self.total_decisions + 1

        self.decision_history.append(decision)
        if len(self.decision_history) > 100:
            self.decision_history = self.decision_history[-100:]

        self.total_decisions += 1

        return decision

    def update_last_decision_outcome(self, outcome: Dict[str, Any]):
        if not self.decision_history:
            return

        self.decision_history[-1]["outcome"] = outcome

        last_action = self.decision_history[-1].get("action")
        if outcome.get("type") == "turn" and last_action in self.DIRECTION_ACTIONS:
            self.pending_turn_direction = last_action
            self.pending_turn_set_frame = self.decision_history[-1].get("frame", 0)
        elif outcome.get("type") in {"movement", "blocked", "interaction", "map_change", "auto_dialogue"}:
            self.pending_turn_direction = None

    def get_decision_count(self) -> int:
        return self.total_decisions

    def get_recent_decisions(self, count: int = 10) -> list[Dict[str, Any]]:
        return self.decision_history[-count:]

    def get_provider_stats(self) -> Optional[Dict[str, Any]]:
        if self.provider is not None:
            stats = self.provider.get_usage_stats()
            stats["turn_completion_overrides"] = self.turn_completion_overrides
            return stats
        return {"turn_completion_overrides": self.turn_completion_overrides}
```

### File: `modules/llm_trainer/llm_providers/base.py`
```python
# Only the modified sections are shown here for brevity in this pack:
# 1) Add a concise hard rule in POKEMON_SYSTEM_PROMPT:
#    "If previous result was ⟳ turn, default next action to same direction unless blocked/interrupt."
# 2) Add a "Pending Turn Completion" section in build_user_prompt() if last outcome.type == 'turn'.
# 3) Include optional response field "turn_completion_ack": true|false.
```

## Integration with AgentMemory
- Memory stays source-of-truth for goals/plan.
- Turn completion state is ephemeral control memory in `Agent`, not long-term semantic memory.
- Optional: when forced override occurs > N times, add memory observation: "navigation instability in current room" for analytics.

## Testing Strategy
### Unit Tests
```python
from modules.llm_trainer.agent import Agent


def test_forces_same_direction_after_turn():
    agent = Agent(use_mock=True)
    agent.decision_history.append({"action": "Left", "frame": 100})
    agent.update_last_decision_outcome({"type": "turn"})
    decision = {"action": "Up", "reasoning": "change"}
    out = agent._apply_turn_completion_guard(decision, {"frame": 101})
    assert out["action"] == "Left"
    assert out["turn_completion_forced"] is True


def test_does_not_force_when_interrupt_state():
    agent = Agent(use_mock=True)
    agent.pending_turn_direction = "Down"
    decision = {"action": "Left", "reasoning": "change"}
    out = agent._apply_turn_completion_guard(decision, {"frame": 200, "in_dialogue": True})
    assert out["action"] == "Left"
    assert agent.pending_turn_direction is None
```

### Integration Tests
- Log pattern should shift from `⟳,⟳,⟳` to `⟳,✓`.
- Check `turn_completion_forced` rate initially non-zero, then decreasing as model learns.

### Metrics
- Turn Completion Rate target: >=90%.
- Position Change Rate target: >=0.4.
- Override Frequency target: declining trend over sessions.

## Failure Modes
1. **False force during scripted interaction**
   - **Detection:** forced move occurs while `in_dialogue` true.
   - **Mitigation:** interrupt-state cancel (already included).
2. **Repeated blocked after turn due wall**
   - **Detection:** pattern `turn -> forced same dir -> blocked`.
   - **Mitigation:** clear pending immediately on blocked (included).

## Implementation Complexity
- Time: 2-4 hours
- Changes: ~1 file major + optional prompt tweaks
- Risk: Low-Medium
- Reversible: Easy (guard method + fields removable)

---

# Solution 2: Prompt-Level Turn Contract + Structured Next-Step Hint
**Category:** Prompt Engineering

## Overview
This solution uses stronger prompt scaffolding: explicit decision contract, explicit "Pending Turn Completion" slot, and examples that map ⟳ to a mandatory same-direction retry on next move. It keeps your architecture unchanged and minimizes runtime complexity, but relies on model compliance.

## Why This Solves Spinning
- Converts an implicit mechanic into explicit per-step instruction with high salience.
- Binds the history symbol and outcome fields to a concrete next action rule.
- Works across providers due simple deterministic phrasing and compact examples.

## Complete Implementation

### File: `modules/llm_trainer/llm_providers/base.py`
```python
"""Base LLM Provider - Abstract interface for all LLM providers"""

import json
import re
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from textwrap import dedent


POKEMON_SYSTEM_PROMPT = dedent("""
    You are an AI playing Pokemon FireRed. You control a trainer in the overworld.

    ## Core Input Rule (Highest Priority)
    If the most recent outcome is type=turn (⟳), your default next action MUST be the same direction
    to complete movement. Only break this rule if there is explicit evidence of interruption
    (dialogue/menu/battle/map transition) or known block in that direction.

    ## Game Mechanics
    - Movement: Up/Down/Left/Right
    - If not facing direction: first press turns only; second same press moves
    - A button: interact/confirm dialogue
    - B button: cancel/exit text

    ## Decision History Symbols
    - ✓ success
    - ✗ blocked
    - ⟳ turn only (step 1/2 complete, step 2 still required)

    ## Response JSON (exactly one object)
    {
      "action": "Up|Down|Left|Right|A|B|WAIT",
      "reasoning": "1 sentence",
      "turn_completion_ack": true|false,
      "goal_update": "optional",
      "observation": "optional",
      "plan": "optional"
    }

    ## Examples
    Example A:
    Last result: ⟳ #73 Left | turned to face Left
    Correct next action: Left

    Example B:
    Last result: ⟳ #73 Up | turned to face Up
    Visible above is N (blocked)
    Correct next action: Left (or another legal alternative)
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
    player = game_state.get("player", {})
    pos = player.get("position", {})
    facing = player.get("facing", "Down")
    party = game_state.get("party", [])

    state_lines = [
        f"Position: ({pos.get('x', '?')}, {pos.get('y', '?')})",
        f"Facing: {facing}",
        f"Map: {player.get('map', '?')}",
    ]
    if map_summary:
        state_lines.append(f"Exploration: {map_summary}")

    traversal_map = vision_data.get("traversal_map", [])
    traversal_str = ""
    if traversal_map:
        for row in traversal_map:
            traversal_str += " ".join(row) + "\n"

    tile_map = vision_data.get("tile_map", [])
    direction_info = _analyze_directions(traversal_map, tile_map, facing)

    history = ""
    for d in recent_decisions[-8:]:
        num = d.get('decision_number', '?')
        action = d.get('action', '?')
        outcome = d.get('outcome', {})

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
            result = "auto dialogue"
        elif outcome.get('success', True):
            symbol = "✓"
            result = outcome.get('reason', 'ok')[:40]
        else:
            symbol = "?"
            result = outcome.get('reason', '')[:40]

        history += f"  {symbol} #{num}: {action:5} | {result}\n"

    pending_turn_str = "None"
    if recent_decisions:
        last = recent_decisions[-1]
        last_outcome = last.get("outcome", {})
        last_action = last.get("action", "?")
        if last_outcome.get("type") == "turn" and last_action in {"Up", "Down", "Left", "Right"}:
            pending_turn_str = (
                f"YES - Last action was {last_action} and only a turn happened. "
                f"Default next action should be {last_action}."
            )

    party_str = ""
    for i, p in enumerate(party[:6]):
        species = p.get('species', '?')
        level = p.get('level', '?')
        hp = p.get('hp', {})
        hp_cur = hp.get('current', '?')
        hp_max = hp.get('max', '?')
        party_str += f"  {i+1}. {species} Lv{level} ({hp_cur}/{hp_max} HP)\n"

    prompt = f"""{memory_context if memory_context else '## Goals\n- Explore and progress through the game'}

## Current State
{chr(10).join('- ' + line for line in state_lines)}

## Pending Turn Completion
- {pending_turn_str}

## What's Around You
{direction_info}

## Traversal Map (P=you, W=walkable, N=blocked, ?=unknown, T=transition, I=interact)
{traversal_str.strip() if traversal_str else '(no traversal data)'}

## Your Pokemon
{party_str.strip() if party_str else '(no pokemon yet)'}

## Recent Actions & Results
{history.strip() if history else '(first decision)'}

## Output Rule Reminder
If Pending Turn Completion says YES, repeat that same direction unless blocked/interrupted.
Return exactly one JSON object.
"""
    return prompt


# parse_llm_response and class BaseLLMProvider unchanged
```

## Integration with AgentMemory
- No new memory schema needed.
- Use existing memory context to stabilize macro goals while prompt contract handles micro turn completion.
- Optional: parse `turn_completion_ack` for analytics.

## Testing Strategy
### Unit Tests
```python
def test_prompt_contains_pending_turn_completion_line():
    from modules.llm_trainer.llm_providers.base import build_user_prompt
    game_state = {"player": {"position": {"x": 1, "y": 1}, "facing": "Up", "map": "Test"}, "party": []}
    vision_data = {"traversal_map": [["N","N","N"],["N","P","W"],["N","N","N"]], "tile_map": []}
    recent = [{"decision_number": 10, "action": "Right", "outcome": {"type": "turn"}}]
    text = build_user_prompt(game_state, vision_data, recent)
    assert "Default next action should be Right" in text
```

### Integration Tests
- Replay identical recorded states through all providers; compare post-turn action agreement.

### Metrics
- Provider-specific Turn Completion Rate (OpenAI/Anthropic/Gemini)
- Token delta per prompt (< +8%)

## Failure Modes
1. **LLM ignores explicit rule**
   - Detection: repeated `turn` outcomes without movement.
   - Mitigation: graduate to Solution 1 or 3.
2. **Prompt bloat**
   - Detection: token cost spike.
   - Mitigation: keep pending section single-line and remove verbose examples.

## Implementation Complexity
- Time: 1-2 hours
- Changes: 1 file
- Risk: Medium (compliance variability)
- Reversible: Easy

---

# Solution 3: Executor-Level Atomic "MoveIntent" Macro (Two-Press Direction)
**Category:** Code Intervention

## Overview
This solution introduces a new action intent (`MOVE_UP`, `MOVE_DOWN`, etc.) executed atomically by `ActionExecutor`: press direction once, sample immediate state/facing, and if it was only a turn, auto-press same direction again in the same decision window. It eliminates spinning by collapsing turn+move into one executor transaction.

## Why This Solves Spinning
- Removes dependency on next LLM decision entirely for turn completion.
- If first press already moved, second press is skipped.
- If first press turned only, second press immediately completes movement.
- Edge cases are handled at execution-time using fresh state checks.

## Complete Implementation

### File: `modules/llm_trainer/action_executor.py`
```python
"""Action Executor - Executes button presses based on agent decisions"""

from typing import Optional
from modules.context import context
from modules.console import console


class ActionExecutor:
    """Executes game actions (button presses) based on agent decisions."""

    VALID_BUTTONS = ["Up", "Down", "Left", "Right", "A", "B", "Start", "Select"]
    MOVE_INTENTS = {
        "MOVE_UP": "Up",
        "MOVE_DOWN": "Down",
        "MOVE_LEFT": "Left",
        "MOVE_RIGHT": "Right",
    }

    def __init__(self):
        self.last_action: Optional[str] = None
        self.action_count = 0
        console.print("[yellow]Action executor initialized[/]")

    def _safe_player_snapshot(self) -> dict:
        try:
            from modules.llm_trainer.memory_reader import MemoryReader
            reader = MemoryReader()
            state = reader.read_full_state()
            player = state.get("player", {})
            pos = player.get("position", {})
            return {
                "x": pos.get("x"),
                "y": pos.get("y"),
                "facing": player.get("facing"),
                "ok": True,
            }
        except Exception:
            return {"x": None, "y": None, "facing": None, "ok": False}

    def _execute_move_intent(self, direction: str) -> bool:
        before = self._safe_player_snapshot()

        context.emulator.press_button(direction)

        mid = self._safe_player_snapshot()
        if not before["ok"] or not mid["ok"]:
            # No state visibility; still do best-effort second press for completion.
            context.emulator.press_button(direction)
            return True

        moved = (before["x"], before["y"]) != (mid["x"], mid["y"])
        turned_only = not moved and before["facing"] != mid["facing"]

        if turned_only:
            context.emulator.press_button(direction)

        return True

    def execute(self, action: str) -> bool:
        action = action.strip()

        if action == "WAIT":
            self.last_action = "WAIT"
            self.action_count += 1
            return True

        if action in self.MOVE_INTENTS:
            direction = self.MOVE_INTENTS[action]
            try:
                ok = self._execute_move_intent(direction)
                self.last_action = action
                self.action_count += 1
                return ok
            except Exception as e:
                console.print(f"[red]Error executing move intent {action}: {e}[/]")
                return False

        if action not in self.VALID_BUTTONS:
            console.print(f"[red]Invalid action: {action}[/]")
            return False

        try:
            context.emulator.press_button(action)
            self.last_action = action
            self.action_count += 1
            return True
        except Exception as e:
            console.print(f"[red]Error executing action {action}: {e}[/]")
            return False

    def get_stats(self) -> dict:
        return {
            "total_actions": self.action_count,
            "last_action": self.last_action
        }
```

### File: `modules/llm_trainer/llm_providers/base.py`
```python
# Update action schema in prompt to include MOVE_* intents:
# "action": "MOVE_UP|MOVE_DOWN|MOVE_LEFT|MOVE_RIGHT|Up|Down|Left|Right|A|B|WAIT"
# Add one line: "Prefer MOVE_* for navigation because it automatically handles turn-then-move."

# Update parse_llm_response valid_actions:
valid_actions = [
    "MOVE_UP", "MOVE_DOWN", "MOVE_LEFT", "MOVE_RIGHT",
    "Up", "Down", "Left", "Right", "A", "B", "Start", "Select", "WAIT"
]
```

### File: `modules/llm_trainer/agent.py`
```python
# No required changes, but optional normalization layer:
# If model outputs Up/Down/Left/Right, rewrite to MOVE_* when in overworld navigation mode.
```

## Integration with AgentMemory
- Memory unchanged; goals/plans still drive direction choice.
- Executor guarantees motor-level completion independent of memory.
- Optional memory event: add observation "move_intent used" when second press triggered for diagnostics.

## Testing Strategy
### Unit Tests
```python
class FakeEmu:
    def __init__(self):
        self.presses = []
    def press_button(self, b):
        self.presses.append(b)


def test_move_intent_second_press_on_turn(monkeypatch):
    from modules.llm_trainer.action_executor import ActionExecutor
    ex = ActionExecutor()

    snapshots = iter([
        {"x": 4, "y": 2, "facing": "Left", "ok": True},
        {"x": 4, "y": 2, "facing": "Up", "ok": True},
    ])
    ex._safe_player_snapshot = lambda: next(snapshots)

    from modules.context import context
    context.emulator = FakeEmu()

    assert ex._execute_move_intent("Up") is True
    assert context.emulator.presses == ["Up", "Up"]
```

### Integration Tests
- Run 100 decisions in house with MOVE_* enabled.
- Verify max consecutive turns <= 2 and exit room <= 20 decisions.

### Metrics
- Spin-streak length
- Turn->movement conversion within same decision window
- Input presses per successful tile (should improve)

## Failure Modes
1. **Double-press overshoot in tight movement windows**
   - **Detection:** unexpected two-tile movement patterns.
   - **Mitigation:** gate second press by immediate snapshot; if moved already, skip second.
2. **State snapshot unavailable**
   - **Detection:** `_safe_player_snapshot.ok == False` frequently.
   - **Mitigation:** fallback to best-effort second press only for MOVE_* intent.

## Implementation Complexity
- Time: 4-8 hours
- Changes: 2-3 files
- Risk: Medium-High (timing-sensitive)
- Reversible: Moderate

---

# Recommended Implementation Order
1. **Start with Solution 1** because it has the best reliability/cost ratio and minimal architecture disruption.
2. **If model compliance is good and you want lower code complexity, add Solution 2 prompt contract** to reduce forced overrides.
3. **Nuclear option: Solution 3** when you need deterministic movement regardless of LLM behavior.

## Quick Wins
- Add one-line pending-turn section to prompt immediately.
- Add override counter metric now (`turn_completion_overrides`).
- Add log alert when `turn` occurs 3+ times in 6 decisions.

## Long-term Improvements
- Train a tiny policy head for low-level movement completion while LLM handles strategy.
- Add provider-level A/B prompt experiments and keep best-performing contract per model.
- Add automated replay harness using recorded state traces to evaluate turn completion before deployment.
