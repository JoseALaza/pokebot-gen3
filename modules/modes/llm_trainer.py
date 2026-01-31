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
        
        # Initialize memory reader
        self.memory_reader = MemoryReader()
        
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
        console.print("[yellow]Phase 2: Testing Memory Reader[/]")
        console.print("[yellow]Watch console for player state updates every second[/]")
        
        while True:
            # Log state periodically for testing
            if self.frame_count - self.last_logged_frame >= self.log_interval:
                # Read lightweight state (faster, for frequent checks)
                state = self.memory_reader.read_lightweight_state()
                
                pos = state['player']['position']
                console.print(
                    f"[green]Frame {state['frame']:6d} | "
                    f"Position: ({pos['x']:2d}, {pos['y']:2d}) | "
                    f"Facing: {state['player']['facing']:5s} | "
                    f"Map: {state['player']['map']}[/]"
                )
                
                # Check if player moved
                if self.memory_reader.has_player_moved():
                    console.print("[cyan]  → Player moved! Reading full state...[/]")
                    
                    # Read full state (includes party info)
                    full_state = self.memory_reader.read_full_state()
                    
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