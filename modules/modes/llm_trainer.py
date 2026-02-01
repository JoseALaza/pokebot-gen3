"""
LLM Trainer Bot Mode

This bot mode allows an LLM to play Pokemon FireRed by:
1. Reading game state (memory)
2. Processing screenshots into tile representations (vision)
3. Making decisions based on state and vision (agent)
4. Executing button presses (action executor)

All decisions are logged for debugging and analysis.
"""

from typing import Generator, Optional, Dict, Any
from modules.modes import BotMode
from modules.console import console
from modules.llm_trainer.memory_reader import MemoryReader
from modules.llm_trainer.vision_processor import VisionProcessor
from modules.llm_trainer.action_executor import ActionExecutor
from modules.llm_trainer.agent import Agent


class LLMTrainerMode(BotMode):
    """
    Bot mode that uses an LLM to play Pokemon.
    
    This mode integrates:
    - Memory reading from pokebot-gen3's extensive memory mapping
    - Vision processing using a custom ResNet model
    - LLM-based decision making (or mock responses for testing)
    - Decision logging and visualization via HTTP server
    """
    
    @staticmethod
    def name() -> str:
        """Return the display name of this bot mode"""
        return "LLM Trainer"
    
    def __init__(self):
        """Initialize the LLM Trainer components"""
        console.print("[bold yellow]Initializing LLM Trainer mode...[/]")
        
        # Initialize components
        self.memory_reader = MemoryReader()
        self.vision_processor = VisionProcessor()
        self.action_executor = ActionExecutor()
        
        # Initialize agent with mock LLM
        # Try different strategies: "random", "scripted_exit_house", "explore"
        self.agent = Agent(use_mock=True, mock_strategy="scripted_exit_house")
        
        # Tracking
        self.frame_count = 0
        self.last_decision_frame = 0
        self.decision_interval = 20  # Make decision every 20 frames
        
        # Outcome tracking
        self.last_decision: Optional[Dict[str, Any]] = None
        self.last_position: Optional[tuple] = None
        self.last_map: Optional[str] = None
        
        console.print("[bold green]LLM Trainer mode initialized successfully![/]")
    
    def _check_action_outcome(
        self,
        decision: Dict[str, Any],
        old_position: tuple,
        new_position: tuple,
        old_map: str,
        new_map: str,
        old_facing: str,
        new_facing: str
    ) -> Dict[str, Any]:
        """
        Check the outcome of an action.
        
        Args:
            decision: The decision that was made
            old_position: Position before action
            new_position: Position after action
            old_map: Map before action
            new_map: Map after action
            old_facing: Facing direction before action
            new_facing: Facing direction after action
            
        Returns:
            Outcome dictionary with success/failure and reason
        """
        action = decision["action"]
        
        # Map change always counts as success
        if old_map != new_map:
            return {
                "success": True,
                "type": "map_change",
                "reason": f"Changed map: {old_map} → {new_map}",
                "position_changed": old_position != new_position,
                "facing_changed": old_facing != new_facing
            }
        
        # For directional actions
        if action in ["Up", "Down", "Left", "Right"]:
            # Check if position changed
            if old_position != new_position:
                return {
                    "success": True,
                    "type": "movement",
                    "reason": f"Moved from {old_position} to {new_position}",
                    "position_changed": True,
                    "facing_changed": old_facing != new_facing
                }
            # Check if facing changed (turn without movement)
            elif old_facing != new_facing:
                return {
                    "success": True,
                    "type": "turn",
                    "reason": f"Turned from {old_facing} to {new_facing}",
                    "position_changed": False,
                    "facing_changed": True
                }
            else:
                # Didn't move or turn - likely blocked
                return {
                    "success": False,
                    "type": "blocked",
                    "reason": f"Could not move {action} - blocked by obstacle",
                    "position_changed": False,
                    "facing_changed": False
                }
        
        # For A button
        elif action == "A":
            # Hard to detect A button outcome without more context
            # For now, consider it successful if executed
            return {
                "success": True,
                "type": "button_press",
                "reason": "Pressed A button",
                "position_changed": old_position != new_position,
                "facing_changed": old_facing != new_facing
            }
        
        # For WAIT
        elif action == "WAIT":
            return {
                "success": True,
                "type": "wait",
                "reason": "Waited",
                "position_changed": False,
                "facing_changed": False
            }
        
        # Unknown action
        else:
            return {
                "success": False,
                "type": "unknown",
                "reason": f"Unknown action: {action}",
                "position_changed": False,
                "facing_changed": False
            }
    
    def run(self) -> Generator:
        """
        Main loop for the LLM Trainer bot mode.
        
        This generator is called every frame by pokebot-gen3's main loop.
        Each yield allows one frame to process.
        """
        
        console.print("[bold cyan]LLM Trainer mode starting...[/]")
        console.print("[yellow]Phase 5: Testing Agent (Mock LLM)[/]")
        console.print("[yellow]Agent will make decisions and track outcomes[/]")
        
        while True:
            # Make decision at intervals
            if self.frame_count - self.last_decision_frame >= self.decision_interval:
                # 1. Read game state BEFORE action
                game_state_before = self.memory_reader.read_full_state()
                old_pos = (game_state_before['player']['position']['x'], 
                          game_state_before['player']['position']['y'])
                old_map = game_state_before['player']['map']
                old_facing = game_state_before['player']['facing']
                
                # 2. Process vision (only if player moved to save CPU)
                vision_data = None
                if self.memory_reader.has_player_moved():
                    vision_data = self.vision_processor.process_frame()
                else:
                    vision_data = {
                        "tile_map": self.vision_processor.last_tile_map or [],
                        "tiles_x": self.vision_processor.tiles_x,
                        "tiles_y": self.vision_processor.tiles_y
                    }
                
                # 3. Agent makes decision
                decision = self.agent.decide(game_state_before, vision_data)
                
                # 4. Execute action
                success = self.action_executor.execute(decision["action"])
                
                # 5. WAIT a few frames for action to complete
                for _ in range(5):
                    yield
                    self.frame_count += 1
                
                # 6. Read game state AFTER action
                game_state_after = self.memory_reader.read_full_state()
                new_pos = (game_state_after['player']['position']['x'],
                          game_state_after['player']['position']['y'])
                new_map = game_state_after['player']['map']
                new_facing = game_state_after['player']['facing']
                
                # 7. Check outcome
                outcome = self._check_action_outcome(
                    decision,
                    old_pos, new_pos,
                    old_map, new_map,
                    old_facing, new_facing
                )
                
                # 8. Log decision and outcome
                if success:
                    outcome_icon = "✓" if outcome["success"] else "✗"
                    outcome_color = "green" if outcome["success"] else "red"
                    
                    console.print(
                        f"[{outcome_color}]{outcome_icon} Decision #{self.agent.get_decision_count():3d}: "
                        f"{decision['action']:5s} | "
                        f"Position: ({new_pos[0]:2d}, {new_pos[1]:2d}) | "
                        f"Facing: {new_facing:5s}[/]"
                    )
                    console.print(f"[dim cyan]  → {decision['reasoning']}[/]")
                    console.print(f"[dim {outcome_color}]  → Outcome: {outcome['reason']}[/]")
                else:
                    console.print(f"[red]✗ Action execution failed: {decision['action']}[/]")
                
                # Update last state after processing
                self.memory_reader.update_last_state()
                
                self.last_decision_frame = self.frame_count
            
            self.frame_count += 1
            yield