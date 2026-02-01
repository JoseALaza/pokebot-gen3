"""Agent - Makes decisions based on game state and vision"""

import random
from typing import Dict, Any, Optional
from datetime import datetime
from modules.console import console


class MockLLM:
    """
    Mock LLM for testing without API calls.
    
    Implements simple strategies:
    - random: Random walk
    - scripted_exit_house: Hardcoded sequence to exit player's house
    - explore: Basic exploration (stay in motion, avoid getting stuck)
    """
    
    STRATEGIES = ["random", "scripted_exit_house", "explore"]
    
    def __init__(self, strategy: str = "random"):
        if strategy not in self.STRATEGIES:
            raise ValueError(f"Unknown strategy: {strategy}. Valid: {self.STRATEGIES}")
        
        self.strategy = strategy
        self.step_count = 0
        
        # Scripted sequence for exiting player's house in FireRed
        # Assumes starting position is facing the stairs/door
        self.exit_house_sequence = [
            "Down", "Down", "Down", "Down", "Down"  # Walk south to exit
        ]
        self.sequence_index = 0
        
        console.print(f"[yellow]Mock LLM initialized with strategy: {strategy}[/]")
    
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
    
    def _scripted_exit_house(self, game_state: Dict[str, Any], vision_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Scripted sequence to exit player's house.
        
        Returns:
            Decision with next scripted action
        """
        # Check if we're still in the house - use proper string check
        map_name = game_state['player']['map']
        in_house = "Player's House" in map_name or "Players House" in map_name
        
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
    - Real LLM APIs (future)
    """
    
    def __init__(self, use_mock: bool = True, mock_strategy: str = "random"):
        self.use_mock = use_mock
        
        if use_mock:
            self.llm = MockLLM(strategy=mock_strategy)
            console.print(f"[yellow]Agent initialized with Mock LLM[/]")
        else:
            # TODO: Initialize real LLM
            raise NotImplementedError("Real LLM not implemented yet")
        
        self.decision_history = []
        self.total_decisions = 0  # Track total count separately from history
    
    def decide(self, game_state: Dict[str, Any], vision_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make a decision based on current state and vision.
        
        Args:
            game_state: Game state from MemoryReader
            vision_data: Vision data from VisionProcessor
            
        Returns:
            Decision dictionary with action, reasoning, metadata
        """
        # Get decision from LLM (mock or real)
        decision = self.llm.decide(game_state, vision_data)
        
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
    
    def get_decision_count(self) -> int:
        """Get total number of decisions made (not capped)"""
        return self.total_decisions
    
    def get_recent_decisions(self, count: int = 10) -> list[Dict[str, Any]]:
        """Get N most recent decisions"""
        return self.decision_history[-count:]