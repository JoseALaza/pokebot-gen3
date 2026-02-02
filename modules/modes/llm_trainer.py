"""
LLM Trainer Bot Mode

This bot mode allows an LLM to play Pokemon FireRed by:
1. Reading game state (memory)
2. Processing screenshots into tile representations (vision)
3. Making decisions based on state and vision (agent)
4. Executing button presses (action executor)
5. Building and maintaining maps of explored areas

All decisions are logged for debugging and analysis.
"""

from pathlib import Path
from typing import Generator, Optional, Dict, Any
from modules.modes import BotMode
from modules.context import context
from modules.console import console
from modules.llm_trainer.memory_reader import MemoryReader
from modules.llm_trainer.vision_processor import VisionProcessor
from modules.llm_trainer.action_executor import ActionExecutor
from modules.llm_trainer.agent import Agent
from modules.llm_trainer.map_manager import MapManager
from modules.llm_trainer.decision_logger import DecisionLogger


class LLMTrainerMode(BotMode):
    """
    Bot mode that uses an LLM to play Pokemon.
    
    This mode integrates:
    - Memory reading from pokebot-gen3's extensive memory mapping
    - Vision processing using a custom ResNet model
    - LLM-based decision making (or mock responses for testing)
    - Map building and traversal tracking
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
        self.map_manager = MapManager()
        
        # Initialize agent with mock LLM
        # Try different strategies: "random", "scripted_exit_house", "explore"
        self.agent = Agent(use_mock=True, mock_strategy="explore")
        
        # Decision logger
        self.decision_logger = DecisionLogger(Path(context.profile.path))
        self.decision_logger.set_session_info(
            agent_strategy="explore",
            llm_provider="mock"
        )

        # Tracking
        self.frame_count = 0
        self.last_decision_frame = 0
        self.decision_interval = 30  # Make decision every 30 frames (~0.5 seconds)
        self.last_blocked_tile: Optional[tuple] = None

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
        console.print("[yellow]Phase 7: Decision Logging[/]")
        console.print("[yellow]Agent will explore and build maps[/]")
        session_info_set = False
        
        while True:
            # Make decision at intervals
            if self.frame_count - self.last_decision_frame >= self.decision_interval:
                # 0. Check if we're in a non-overworld state
                game_state_type = self.memory_reader.get_game_state_type()
                if game_state_type == "battle":
                    console.print("[red]In battle! Pausing LLM decisions.[/]")
                    self.last_decision_frame = self.frame_count
                    self.frame_count += 1
                    yield
                    continue
                elif game_state_type == "menu":
                    console.print("[yellow]In menu. Pressing B to exit.[/]")
                    self.action_executor.execute("B")
                    for _ in range(10):
                        yield
                        self.frame_count += 1
                    self.last_decision_frame = self.frame_count
                    continue

                # 1. Read game state BEFORE action
                game_state_before = self.memory_reader.read_full_state()
                old_pos = (game_state_before['player']['position']['x'],
                          game_state_before['player']['position']['y'])
                old_map = game_state_before['player']['map']
                old_facing = game_state_before['player']['facing']

                # Set session start info on first decision
                if not session_info_set:
                    self.decision_logger.set_session_info(
                        start_map=old_map,
                        start_position=[old_pos[0], old_pos[1]]
                    )
                    session_info_set = True
                
                # Load/switch map if needed
                current_map_key = self.map_manager._get_map_key(
                    game_state_before['player']['map_group'],
                    game_state_before['player']['map_number']
                )
                
                if self.map_manager.current_map_key != current_map_key:
                    old_map_key = self.map_manager.current_map_key
                    self.map_manager.save_map()  # Save old map if exists
                    self.map_manager.load_map(
                        game_state_before['player']['map'],
                        game_state_before['player']['map_group'],
                        game_state_before['player']['map_number']
                    )
                    console.print(f"[magenta]{self.map_manager.get_map_summary()}[/]")
                    # Increment visit count
                    self.map_manager.current_map_data['visit_count'] += 1
                    # Record map transition
                    if old_map_key is not None:
                        self.map_manager.handle_map_transition(
                            old_map_key,
                            old_pos,
                            old_facing,
                            current_map_key,
                            (game_state_before['player']['position']['x'],
                             game_state_before['player']['position']['y']),
                            old_facing
                        )
                
                # 2. Process vision and update tile map
                vision_data = self.vision_processor.process_frame()
                
                # Update tile map with current screen
                self.map_manager.update_tile_map_from_screen(
                    old_pos[0],
                    old_pos[1],
                    vision_data['tile_map']
                )
                
                # Mark current position as player
                self.map_manager.set_traversal_at(
                    old_pos[0],
                    old_pos[1],
                    self.map_manager.PLAYER
                )
                
                # 3. Agent makes decision
                decision = self.agent.decide(game_state_before, vision_data)
                
                # 4. Execute action
                success = self.action_executor.execute(decision["action"])
                
                # 5. WAIT for action to complete with stabilization check
                last_check_pos = None
                for i in range(12):
                    yield
                    self.frame_count += 1
                    if i >= 3:
                        check_state = self.memory_reader.read_full_state()
                        check_pos = (check_state['player']['position']['x'],
                                     check_state['player']['position']['y'])
                        if check_pos == last_check_pos:
                            break
                        last_check_pos = check_pos
                
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
                
                # 8. Update traversal map based on outcome
                if outcome["type"] == "movement":
                    distance = abs(new_pos[0] - old_pos[0]) + abs(new_pos[1] - old_pos[1])

                    if distance > 1:
                        # Likely a ledge jump
                        console.print(f"[magenta]Detected multi-tile movement! Distance: {distance}[/]")
                        self.map_manager.set_traversal_at(
                            old_pos[0],
                            old_pos[1],
                            self.map_manager.LEDGE
                        )
                    else:
                        # Normal movement - mark old position as walkable
                        self.map_manager.set_traversal_at(
                            old_pos[0],
                            old_pos[1],
                            self.map_manager.WALKABLE
                        )
                    # Mark new position as player
                    self.map_manager.set_traversal_at(
                        new_pos[0],
                        new_pos[1],
                        self.map_manager.PLAYER
                    )
                    # Reset blocked tracking on successful movement
                    self.last_blocked_tile = None

                elif outcome["type"] == "turn":
                    # Just a turn, player is still here - mark as player
                    self.map_manager.set_traversal_at(
                        old_pos[0],
                        old_pos[1],
                        self.map_manager.PLAYER
                    )

                elif outcome["type"] == "blocked":
                    # Calculate target tile and mark as blocked
                    action_direction = decision["action"]
                    target_x, target_y = self.map_manager.calculate_target_tile(
                        old_pos[0],
                        old_pos[1],
                        action_direction
                    )
                    if (target_x, target_y) == self.last_blocked_tile:
                        console.print(
                            f"[dim]  → Tile ({target_x}, {target_y}) already marked as BLOCKED[/]"
                        )
                    else:
                        self.map_manager.set_traversal_at(
                            target_x,
                            target_y,
                            self.map_manager.BLOCKED
                        )
                        self.last_blocked_tile = (target_x, target_y)
                        console.print(
                            f"[red]  → Marked tile ({target_x}, {target_y}) as BLOCKED[/]"
                        )
                
                elif outcome["type"] == "map_change":
                    # Mark old position as traversal tile in old map
                    self.map_manager.set_traversal_at(
                        old_pos[0],
                        old_pos[1],
                        self.map_manager.TRAVERSAL
                    )
                    console.print(
                        f"[magenta]Map transition: "
                        f"{old_map} ({old_pos[0]},{old_pos[1]}) → "
                        f"{new_map} ({new_pos[0]},{new_pos[1]})[/]"
                    )
                
                # 9. Save map periodically
                if self.agent.get_decision_count() % 10 == 0:
                    self.map_manager.save_map()
                
                # 10. Log decision to file
                self.decision_logger.log_decision(
                    decision_number=self.agent.get_decision_count(),
                    frame=self.frame_count,
                    game_state_before=game_state_before,
                    vision_data=vision_data,
                    decision=decision,
                    execution_success=success,
                    outcome=outcome,
                    game_state_after=game_state_after
                )

                # 11. Log decision to console
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