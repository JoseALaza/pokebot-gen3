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
from modules.llm_trainer.llm_state import llm_state


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
        
        # Initialize agent
        # Strategies: "explore", "random", "scripted_exit_house", "scripted"
        # self.agent = Agent(use_mock=True, mock_strategy="scripted")
        # Real LLM:   Agent(use_mock=False, provider="openai", model="gpt-4o-mini")
        memory_path = str(Path(context.profile.path) / "llm_trainer" / "agent_memory.json")
        # Options: "anthropic", "openai", "gemini"
        self.agent = Agent(
            use_mock=False,
            provider="ollama",
            model="llama3.1:8b"
        )
        

        # ── Define your test script here (only for MockLLM) ──
        # Valid actions: Up, Down, Left, Right, A, B, WAIT
        # on_end: "stop" (WAIT forever), "loop" (restart), "explore" (switch to explore)
        if self.agent.use_mock:
            self.agent.llm.set_script([
                "Up"                           # Turn + interact test
            ], on_end="stop")

        # Decision logger
        self.decision_logger = DecisionLogger(Path(context.profile.path))
        strategy = self.agent.llm.strategy if self.agent.use_mock else self.agent.provider_name
        self.decision_logger.set_session_info(
            agent_strategy=strategy,
            llm_provider=self.agent.provider_name
        )

        # Shared state for HTTP visualization
        llm_state.session_id = self.decision_logger.session_id
        llm_state.agent_strategy = strategy

        # Tracking
        self.frame_count = 0
        self.last_decision_frame = 0
        self.decision_interval = 5*60  # Make decision every 30 frames (~0.5 seconds)
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
        console.print("[yellow]Phase 9: LLM Integration Complete[/]")
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

                elif game_state_type == "dialogue":
                    # Smart dialogue handling: keep pressing A until we exit dialogue
                    dialogue_presses = 0
                    max_dialogue_presses = 50  # Safety limit

                    console.print("[cyan]Dialogue detected. Advancing...[/]")

                    while dialogue_presses < max_dialogue_presses:
                        self.action_executor.execute("A")
                        dialogue_presses += 1

                        # Wait for dialogue to end (5 consecutive frames without dialogue)
                        frames_without_dialogue = 0
                        for _ in range(30):
                            yield
                            self.frame_count += 1

                            if not self.memory_reader.is_dialogue_active():
                                frames_without_dialogue += 1
                                if frames_without_dialogue >= 5:
                                    break
                            else:
                                frames_without_dialogue = 0

                        if frames_without_dialogue >= 5:
                            console.print(f"[green]Dialogue ended ({dialogue_presses} presses).[/]")
                            break

                        if dialogue_presses % 10 == 0:
                            console.print(f"[cyan]Still in dialogue... ({dialogue_presses}x)[/]")

                    if dialogue_presses >= max_dialogue_presses:
                        console.print(f"[yellow]Dialogue limit reached. Trying B to exit.[/]")
                        for _ in range(10):
                            self.action_executor.execute("B")
                            for _ in range(5):
                                yield
                                self.frame_count += 1

                    self.last_decision_frame = self.frame_count
                    continue

                elif game_state_type == "naming_screen":
                    naming_info = self.memory_reader.get_naming_screen_info()
                    if naming_info:
                        console.print(
                            f"[cyan]Naming screen active. "
                            f"Current input: '{naming_info['current_input']}' "
                            f"State: {naming_info['state']}[/]"
                        )
                        # For now, just press A to accept default or skip
                        # TODO: Integrate with LLM to generate names
                        if naming_info['is_ready_for_input']:
                            self.action_executor.execute("Start")  # Go to OK button
                        else:
                            self.action_executor.execute("A")
                    for _ in range(10):
                        yield
                        self.frame_count += 1
                    self.last_decision_frame = self.frame_count
                    continue

                elif game_state_type == "map_transition":
                    # Wait for map transition to complete
                    for _ in range(5):
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
                    # Map changed - this can happen on first frame or if outcome handler
                    # didn't catch a transition (e.g., scripted warp, teleport)
                    self.map_manager.save_map()  # Save old map if exists
                    self.map_manager.load_map(
                        game_state_before['player']['map'],
                        game_state_before['player']['map_group'],
                        game_state_before['player']['map_number']
                    )
                    console.print(f"[magenta]{self.map_manager.get_map_summary()}[/]")
                    # Increment visit count
                    self.map_manager.current_map_data['visit_count'] += 1
                    # Note: handle_map_transition is called in the outcome handler
                    # where we have correct old/new positions
                
                # 2. Process vision and update tile map
                vision_data = self.vision_processor.process_frame()

                # Update tile map with current screen
                self.map_manager.update_tile_map_from_screen(
                    old_pos[0],
                    old_pos[1],
                    vision_data['tile_map']
                )

                # Mark current position as player (but preserve traversal markers)
                current_marker = self.map_manager.get_traversal_at(old_pos[0], old_pos[1])
                if current_marker != self.map_manager.TRAVERSAL:
                    self.map_manager.set_traversal_at(
                        old_pos[0],
                        old_pos[1],
                        self.map_manager.PLAYER
                    )

                # 2b. Add traversal map view to vision_data for LLM context
                vision_data['traversal_map'] = self.map_manager.get_traversal_view(
                    old_pos[0], old_pos[1], radius=4
                )
                # Also add the tile view from map_manager (may differ from screen vision)
                vision_data['tile_view'] = self.map_manager.get_tile_view(
                    old_pos[0], old_pos[1], radius=4
                )

                # 2c. Build traversal context with connections info
                traversal_context = {
                    'connections': []
                }
                # Get known connections from current map
                if self.map_manager.current_map_key:
                    for conn in self.map_manager.map_graph.connections:
                        if conn['from_map'] == self.map_manager.current_map_key:
                            traversal_context['connections'].append({
                                'direction': conn['direction'],
                                'exit_tile': conn['from_tile'],
                                'target_map': conn['to_map']
                            })

                # 3. Agent makes decision
                map_summary = self.map_manager.get_map_summary()
                decision = self.agent.decide(
                    game_state_before,
                    vision_data,
                    map_summary=map_summary,
                    traversal_context=traversal_context,
                    map_key=current_map_key
                )
                
                # 4. Execute action
                success = self.action_executor.execute(decision["action"])
                
                # 5. WAIT for action to complete with stabilization check
                # Track both position AND map to detect transitions
                last_check_pos = None
                original_map_key = self.map_manager._get_map_key(
                    game_state_before['player']['map_group'],
                    game_state_before['player']['map_number']
                )
                original_pos = old_pos
                stable_frames = 0
                exit_reason = "timeout"

                # For directional actions, wait minimum frames before allowing "stable" exit
                # This prevents exiting during black screen transitions
                is_directional = decision["action"] in ["Up", "Down", "Left", "Right"]
                min_wait_frames = 25 if is_directional else 5

                for i in range(60):  # Max wait for map transitions (60 frames = ~1 sec)
                    yield
                    self.frame_count += 1

                    if i >= 3:
                        check_state = self.memory_reader.read_full_state()
                        check_pos = (check_state['player']['position']['x'],
                                     check_state['player']['position']['y'])
                        check_map_key = self.map_manager._get_map_key(
                            check_state['player']['map_group'],
                            check_state['player']['map_number']
                        )

                        # Detect map change
                        if check_map_key != original_map_key:
                            # Wait a few more frames for transition to complete
                            for _ in range(10):
                                yield
                                self.frame_count += 1
                            exit_reason = "map_change"
                            break

                        # Check for position stabilization (normal movement)
                        # Only allow stable exit after minimum wait frames
                        if i >= min_wait_frames:
                            if check_pos == last_check_pos:
                                stable_frames += 1
                                if stable_frames >= 3:  # Stable for 3 consecutive checks
                                    exit_reason = "stable"
                                    break
                            else:
                                stable_frames = 0

                        last_check_pos = check_pos

                # Final transition check: if directional action didn't move player,
                # wait extra time and re-check for map transition (black screen delays)
                if is_directional and exit_reason == "stable" and last_check_pos == original_pos:
                    # Wait additional frames for potential map transition
                    for extra_wait in range(120):  # Up to 2 more seconds
                        yield
                        self.frame_count += 1
                        if extra_wait % 10 == 0:
                            check_state = self.memory_reader.read_full_state()
                            check_map_key = self.map_manager._get_map_key(
                                check_state['player']['map_group'],
                                check_state['player']['map_number']
                            )
                            if check_map_key != original_map_key:
                                exit_reason = "delayed_map_change"
                                # Wait a bit more for full stabilization
                                for _ in range(15):
                                    yield
                                    self.frame_count += 1
                                break
                
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

                # 7b. Check if 'A' button triggered dialogue (interactable detection)
                # Note: is_dialogue_active() returns True when text FINISHES printing and
                # the game waits for input. Detection time varies based on dialogue length:
                # - Short dialogue (~50-100 frames)
                # - Long dialogue (~150-200+ frames)
                if decision["action"] == "A" and outcome["type"] == "button_press":
                    dialogue_detected = False
                    for dialogue_check in range(180):  # Wait up to 180 frames (~3 seconds)
                        yield
                        self.frame_count += 1
                        if self.memory_reader.is_dialogue_active():
                            dialogue_detected = True
                            break

                    if dialogue_detected:
                        outcome["type"] = "interaction"
                        outcome["reason"] = "Interacted with object/NPC - dialogue appeared"
                        # Mark tile in front of player as interactable
                        target_x, target_y = self.map_manager.calculate_target_tile(
                            old_pos[0], old_pos[1], old_facing
                        )
                        self.map_manager.set_traversal_at(
                            target_x, target_y,
                            self.map_manager.INTERACTABLE
                        )
                        console.print(
                            f"[green]  → Marked tile ({target_x}, {target_y}) as INTERACTABLE[/]"
                        )

                # 7b2. Check if movement triggered auto-dialogue (walk-on trigger tiles)
                # Some tiles (signs walked into, trigger NPCs) start dialogue without A press
                if outcome["type"] == "movement":
                    # Brief check for auto-dialogue (these trigger faster than A-press dialogue)
                    auto_dialogue_detected = False
                    for dialogue_check in range(60):  # Wait up to 60 frames (~1 second)
                        yield
                        self.frame_count += 1
                        if self.memory_reader.is_dialogue_active():
                            auto_dialogue_detected = True
                            break

                    if auto_dialogue_detected:
                        outcome["type"] = "auto_dialogue"
                        outcome["reason"] = "Stepped on trigger tile - dialogue appeared automatically"
                        # Mark the tile we moved TO as interactable (auto-trigger)
                        self.map_manager.set_traversal_at(
                            new_pos[0], new_pos[1],
                            self.map_manager.INTERACTABLE
                        )
                        console.print(
                            f"[cyan]  → Auto-dialogue triggered! Marked tile ({new_pos[0]}, {new_pos[1]}) as INTERACTABLE[/]"
                        )

                # 7c. Update the decision with its outcome (for LLM learning)
                self.agent.update_last_decision_outcome(outcome)

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
                        # Normal movement - mark old position based on what it was
                        # Preserve traversal markers (T), otherwise mark as walkable (W)
                        old_marker = self.map_manager.get_traversal_at(old_pos[0], old_pos[1])
                        if old_marker != self.map_manager.TRAVERSAL:
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

                elif outcome["type"] == "auto_dialogue":
                    # Movement that triggered auto-dialogue
                    # Mark old position as walkable (we came from there)
                    old_marker = self.map_manager.get_traversal_at(old_pos[0], old_pos[1])
                    if old_marker != self.map_manager.TRAVERSAL:
                        self.map_manager.set_traversal_at(
                            old_pos[0], old_pos[1],
                            self.map_manager.WALKABLE
                        )
                    # New position already marked as INTERACTABLE in step 7b2
                    # Don't overwrite it with PLAYER
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
                    # Bug fix #1: Mark traversal tile in OLD map correctly
                    # The traversal tile is where the player stepped TO (in direction they faced)
                    # NOT where they were standing
                    action_direction = decision["action"]
                    if action_direction in ["Up", "Down", "Left", "Right"]:
                        traversal_x, traversal_y = self.map_manager.calculate_target_tile(
                            old_pos[0], old_pos[1], action_direction
                        )
                    else:
                        # If action wasn't directional (e.g., A button on door), use old_pos
                        traversal_x, traversal_y = old_pos[0], old_pos[1]

                    # Mark the traversal tile as T in the OLD map (before we switch maps)
                    self.map_manager.set_traversal_at(traversal_x, traversal_y, self.map_manager.TRAVERSAL)
                    # Mark where player WAS standing as walkable
                    self.map_manager.set_traversal_at(old_pos[0], old_pos[1], self.map_manager.WALKABLE)

                    # Get old map key before saving/switching
                    old_map_key = self.map_manager.current_map_key

                    # Clear player's tile in old map before saving
                    # (so we don't leave "player" marker in the old map)
                    self.map_manager.clear_player_tile(old_pos[0], old_pos[1])

                    # Save the old map with correct traversal markings
                    self.map_manager.save_map()

                    # Calculate new map key
                    new_map_key = self.map_manager._get_map_key(
                        game_state_after['player']['map_group'],
                        game_state_after['player']['map_number']
                    )

                    # Record the connection with correct positions
                    # Exit tile = where player stepped TO in old map (traversal_x, traversal_y)
                    # Entry tile = where player appeared in new map (new_pos)
                    if old_map_key is not None:
                        self.map_manager.map_graph.add_connection(
                            old_map_key,
                            (traversal_x, traversal_y),  # Exit tile in old map
                            new_map_key,
                            new_pos,  # Entry tile in new map
                            action_direction if action_direction in ["Up", "Down", "Left", "Right"] else old_facing
                        )
                        console.print(
                            f"[magenta]Added connection: "
                            f"{old_map_key} ({traversal_x},{traversal_y}) → "
                            f"{new_map_key} {new_pos}[/]"
                        )

                    # Load the new map
                    self.map_manager.load_map(
                        new_map,
                        game_state_after['player']['map_group'],
                        game_state_after['player']['map_number']
                    )
                    self.map_manager.current_map_data['visit_count'] += 1

                    # Mark entry tile as traversal point in new map
                    # This is where warps drop you INTO the map
                    self.map_manager.set_traversal_at(
                        new_pos[0],
                        new_pos[1],
                        self.map_manager.TRAVERSAL
                    )

                    console.print(
                        f"[magenta]Map transition: "
                        f"{old_map} T@({traversal_x},{traversal_y}) → "
                        f"{new_map} T@({new_pos[0]},{new_pos[1]})[/]"
                    )
                
                # 9. Save map periodically
                if self.agent.get_decision_count() % 2 == 0:
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

                # 11. Update shared state for HTTP visualization
                llm_state.update(
                    position={"x": new_pos[0], "y": new_pos[1]},
                    map_name=new_map,
                    map_key=self.map_manager.current_map_key or "",
                    facing=new_facing,
                    game_state_type="overworld",
                    total_decisions=self.agent.get_decision_count(),
                    decision=decision,
                    outcome=outcome,
                    map_summary=self.map_manager.get_map_summary(),
                    map_connections_count=len(self.map_manager.map_graph.connections)
                )

                # 12. Log decision to console
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