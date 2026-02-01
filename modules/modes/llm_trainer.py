"""
LLM Trainer Bot Mode

This bot mode allows an LLM to play Pokemon FireRed by:
1. Reading game state (memory)
2. Processing screenshots into tile representations (vision)
3. Making decisions based on state and vision (agent)
4. Executing button presses (action executor)

All decisions are logged for debugging and analysis.
"""

import random
from typing import Generator
from modules.modes import BotMode
from modules.console import console
from modules.llm_trainer.memory_reader import MemoryReader
from modules.llm_trainer.vision_processor import VisionProcessor
from modules.llm_trainer.action_executor import ActionExecutor


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
        
        # Tracking
        self.frame_count = 0
        self.last_action_frame = 0
        self.action_interval = 30  # Execute action every 30 frames (~0.5 seconds)
        
        console.print("[bold green]LLM Trainer mode initialized successfully![/]")
    
    def run(self) -> Generator:
        """
        Main loop for the LLM Trainer bot mode.
        
        This generator is called every frame by pokebot-gen3's main loop.
        Each yield allows one frame to process.
        """
        
        console.print("[bold cyan]LLM Trainer mode starting...[/]")
        console.print("[yellow]Phase 4: Testing Action Executor[/]")
        console.print("[yellow]Bot will execute random actions - watch it move![/]")
        
        while True:
            # Execute random action at intervals
            if self.frame_count - self.last_action_frame >= self.action_interval:
                # Read current state
                state = self.memory_reader.read_lightweight_state()
                
                # Choose random action (favor movement over other buttons)
                actions = ["Up", "Down", "Left", "Right", "A", "Wait"]
                weights = [25, 25, 25, 25, 5, 5]  # Prefer directional movement
                action = random.choices(actions, weights=weights)[0]
                
                # Execute action
                success = self.action_executor.execute(action)
                
                # Log action and result
                pos = state['player']['position']
                stats = self.action_executor.get_stats()
                
                if success:
                    console.print(
                        f"[green]Action #{stats['total_actions']:3d}: {action:5s} | "
                        f"Position: ({pos['x']:2d}, {pos['y']:2d}) | "
                        f"Facing: {state['player']['facing']:5s} | "
                        f"Map: {state['player']['map']}[/]"
                    )
                else:
                    console.print(f"[red]Action failed: {action}[/]")
                
                self.last_action_frame = self.frame_count
            
            self.frame_count += 1
            yield