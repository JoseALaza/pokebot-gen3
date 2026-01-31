"""
LLM Trainer Bot Mode

This bot mode allows an LLM to play Pokemon FireRed by:
1. Reading game state (memory)
2. Processing screenshots into tile representations (vision)
3. Making decisions based on state and vision (agent)
4. Executing button presses (action executor)

All decisions are logged for debugging and analysis.
"""

from typing import Generator
from modules.modes import BotMode
from modules.console import console
from modules.llm_trainer.memory_reader import MemoryReader
from modules.llm_trainer.vision_processor import VisionProcessor


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
        
        # Tracking
        self.frame_count = 0
        self.last_logged_frame = 0
        self.log_interval = 60  # Log every 60 frames (1 second at 1x speed)
        
        console.print("[bold green]LLM Trainer mode initialized successfully![/]")
    
    def run(self) -> Generator:
        """
        Main loop for the LLM Trainer bot mode.
        
        This generator is called every frame by pokebot-gen3's main loop.
        Each yield allows one frame to process.
        """
        
        console.print("[bold cyan]LLM Trainer mode starting...[/]")
        console.print("[yellow]Phase 3: Testing Vision Processor[/]")
        console.print("[yellow]Watch console for tile map updates[/]")
        
        while True:
            # Log state periodically for testing
            if self.frame_count - self.last_logged_frame >= self.log_interval:
                # Read lightweight state
                state = self.memory_reader.read_lightweight_state()
                
                pos = state['player']['position']
                console.print(
                    f"[green]Frame {state['frame']:6d} | "
                    f"Position: ({pos['x']:2d}, {pos['y']:2d}) | "
                    f"Facing: {state['player']['facing']:5s} | "
                    f"Map: {state['player']['map']}[/]"
                )
                
                # Check if map changed
                if self.memory_reader.has_map_changed():
                    old_map = self.memory_reader.last_state.map_name
                    new_map = state['player']['map']
                    console.print(f"[bold magenta]  → MAP CHANGED: {old_map} → {new_map}[/]")
                
                # Check if player moved
                if self.memory_reader.has_player_moved():
                    console.print("[cyan]  → Player moved! Reading full state...[/]")
                    
                    # Read full state
                    full_state = self.memory_reader.read_full_state()
                    
                    # Process vision
                    console.print("[blue]  → Processing vision...[/]")
                    vision_data = self.vision_processor.process_frame()
                    
                    # Show debug info
                    debug_info = self.vision_processor.get_debug_info()
                    console.print(f"[dim blue]  → Screenshot: {debug_info['screenshot_shape']}, "
                                f"dtype={debug_info['screenshot_dtype']}, "
                                f"range=[{debug_info['screenshot_min_value']}-{debug_info['screenshot_max_value']}], "
                                f"mean={debug_info['screenshot_mean_value']:.1f}[/]")
                    console.print(f"[dim blue]  → Tile map: {debug_info['last_tile_map_dimensions']} grid[/]")

                    # Show tile statistics
                    tile_stats = self.vision_processor.get_tile_statistics(vision_data['tile_map'])
                    console.print(f"[blue]  → Tile types detected: {tile_stats}[/]")
                    
                    # Show a sample of the tile map (first 3 rows)
                    console.print("[blue]  → Tile map sample (first 3 rows):[/]")
                    for i, row in enumerate(vision_data['tile_map'][:3]):
                        console.print(f"[dim]    Row {i}: {' '.join(row[:10])}...[/]")
                    
                    # Log party info
                    console.print(f"[blue]  → Party size: {full_state['party_size']}[/]")
                    if full_state['party_size'] > 0:
                        first_pokemon = full_state['party'][0]
                        console.print(
                            f"[blue]  → First Pokemon: {first_pokemon['species']} "
                            f"Lv.{first_pokemon['level']} "
                            f"({first_pokemon['hp']['current']}/{first_pokemon['hp']['max']} HP)[/]"
                        )
                    
                    # Update last known state
                    self.memory_reader.update_last_state()
                
                self.last_logged_frame = self.frame_count
            
            self.frame_count += 1
            yield