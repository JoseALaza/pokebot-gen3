"""Action Executor - Executes button presses based on agent decisions"""

from typing import Optional
from modules.context import context
from modules.console import console


class ActionExecutor:
    """
    Executes game actions (button presses) based on agent decisions.
    
    Supported actions:
    - Directional: UP, DOWN, LEFT, RIGHT
    - Buttons: A, B, START, SELECT
    - Special: WAIT (do nothing)
    """
    
    VALID_BUTTONS = ["Up", "Down", "Left", "Right", "A", "B", "Start", "Select"]
    
    def __init__(self):
        self.last_action: Optional[str] = None
        self.action_count = 0
        console.print("[yellow]Action executor initialized[/]")
    
    def execute(self, action: str) -> bool:
        """
        Execute an action (button press).
        
        Args:
            action: Button to press (e.g., "UP", "A", "WAIT")
            
        Returns:
            True if action executed successfully, False otherwise
        """
        action = action.strip()
        
        # Handle WAIT action (do nothing)
        if action == "WAIT":
            self.last_action = "WAIT"
            self.action_count += 1
            return True
        
        # Validate action
        if action not in self.VALID_BUTTONS:
            console.print(f"[red]Invalid action: {action}[/]")
            return False
        
        # Execute button press
        try:
            context.emulator.press_button(action)
            self.last_action = action
            self.action_count += 1
            return True
            
        except Exception as e:
            console.print(f"[red]Error executing action {action}: {e}[/]")
            return False
    
    def get_stats(self) -> dict:
        """
        Get action execution statistics.
        
        Returns:
            Dictionary with execution stats
        """
        return {
            "total_actions": self.action_count,
            "last_action": self.last_action
        }