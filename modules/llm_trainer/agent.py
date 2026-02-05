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
        """
        Set a custom script of actions to execute.

        Args:
            actions: List of action strings, e.g. ["Down", "Down", "Right", "A"]
            on_end: What to do when script ends: "stop", "loop", or "explore"
        """
        self.script = actions
        self.script_index = 0
        self.script_on_end = on_end
        self.strategy = "scripted"
        console.print(f"[yellow]Script loaded: {len(actions)} actions, on_end={on_end}[/]")
        console.print(f"[dim yellow]  Actions: {', '.join(actions[:20])}{'...' if len(actions) > 20 else ''}[/]")
    
    def decide(self, game_state: Dict[str, Any], vision_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make a decision based on current state.
        
        Args:
            game_state: Current game state from MemoryReader
            vision_data: Processed vision from VisionProcessor
            
        Returns:
            Decision dict with action, reasoning, confidence
        """
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
        """
        Random walk strategy.
        
        Returns:
            Decision with random action
        """
        actions = ["Up", "Down", "Left", "Right", "A", "WAIT"]
        weights = [20, 20, 20, 20, 10, 10]  # Prefer movement over A/WAIT
        
        action = random.choices(actions, weights=weights)[0]
        
        return {
            "action": action,
            "reasoning": f"Random walk strategy - step {self.step_count}, chose {action}",
            "confidence": 0.5,
            "strategy": "random",
            "step": self.step_count
        }
    
    def _scripted(self, game_state: Dict[str, Any], vision_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute actions from a custom script list.

        Returns:
            Decision with the next scripted action
        """
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
        """
        Scripted sequence to exit player's house.
        
        Returns:
            Decision with next scripted action
        """
        # Check if we're still in the house - use proper string check
        map_name = game_state['player']['map']
        in_house = "Player’s House" in map_name or "Players House" in map_name
        console.print(in_house, map_name)
        if not in_house:
            # We've exited! Switch to explore mode
            console.print(f"[bold green]Successfully exited house! Current map: {map_name}[/]")
            console.print("[bold green]Switching to explore mode.[/]")
            self.strategy = "explore"
            return self._explore(game_state, vision_data)
        
        # Execute scripted sequence
        if self.sequence_index >= len(self.exit_house_sequence):
            # Sequence complete but still in house - maybe got stuck
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
        """
        Basic exploration strategy.
        
        Goals:
        - Keep moving (prefer continuing in same direction)
        - If can't move, try another direction
        - Avoid A button spam
        
        Returns:
            Decision with exploration action
        """
        # Get current facing direction
        facing = game_state['player']['facing']
        
        # 60% chance to continue in current direction
        # 30% chance to try a different direction  
        # 10% chance to press A or WAIT
        choice = random.random()
        
        if choice < 0.6:
            # Continue current direction
            action = facing
            reasoning = f"Continuing {facing}"
        elif choice < 0.9:
            # Try a different direction
            directions = ["Up", "Down", "Left", "Right"]
            directions.remove(facing)  # Remove current direction
            action = random.choice(directions)
            reasoning = f"Changing direction from {facing} to {action}"
        else:
            # Press A or WAIT
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
    """
    Agent that makes decisions for the LLM Trainer.

    Can use:
    - MockLLM for testing (multiple strategies)
    - Real LLM APIs (openai, anthropic, gemini)

    Includes AgentMemory for persistent goals and observations.
    """

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

        # Initialize memory system
        from pathlib import Path
        from modules.llm_trainer.agent_memory import AgentMemory
        save_path = Path(memory_save_path) if memory_save_path else None
        self.memory = AgentMemory(save_path=save_path)
        console.print(f"[yellow]Agent memory initialized[/]")

    def decide(
        self,
        game_state: Dict[str, Any],
        vision_data: Dict[str, Any],
        map_summary: Optional[str] = None,
        traversal_context: Optional[Dict[str, Any]] = None,
        map_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Make a decision based on current state and vision.

        Args:
            game_state: Game state from MemoryReader
            vision_data: Vision data from VisionProcessor (should include traversal_map)
            map_summary: Current map exploration summary string
            traversal_context: Additional context like known connections
            map_key: Current map identifier for memory tracking

        Returns:
            Decision dictionary with action, reasoning, metadata
        """
        # Track position for stuck detection
        pos = game_state.get("player", {}).get("position", {})
        if map_key and pos:
            self.memory.record_position(map_key, pos.get("x", 0), pos.get("y", 0))

        # Get exploration priority
        traversal_map = vision_data.get("traversal_map", [])
        exploration_priority = self.memory.get_exploration_priority(map_key or "", traversal_map)

        # Get memory context for prompt
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

        # Process any memory updates from LLM response
        self.memory.parse_llm_memory_updates(decision)

        # Add metadata
        decision["timestamp"] = datetime.now().isoformat()
        decision["frame"] = game_state.get("frame", 0)
        decision["decision_number"] = self.total_decisions + 1

        # Store in history (keep last 100 for memory efficiency)
        self.decision_history.append(decision)
        if len(self.decision_history) > 100:
            self.decision_history = self.decision_history[-100:]

        # Increment total counter
        self.total_decisions += 1

        return decision

    def update_last_decision_outcome(self, outcome: Dict[str, Any]):
        """
        Update the most recent decision with its outcome.
        This is called after the action is executed and we know the result.

        Args:
            outcome: The outcome dict from _check_action_outcome
        """
        if self.decision_history:
            self.decision_history[-1]["outcome"] = outcome
    
    def get_decision_count(self) -> int:
        """Get total number of decisions made (not capped)"""
        return self.total_decisions
    
    def get_recent_decisions(self, count: int = 10) -> list[Dict[str, Any]]:
        """Get N most recent decisions"""
        return self.decision_history[-count:]

    def get_provider_stats(self) -> Optional[Dict[str, Any]]:
        """Get LLM provider usage stats, or None if using mock"""
        if self.provider is not None:
            return self.provider.get_usage_stats()
        return None