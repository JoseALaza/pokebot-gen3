"""Memory Reader - Extracts game state for LLM consumption"""

from dataclasses import dataclass
from typing import Optional, Dict, Any
from modules.context import context
from modules.memory import get_game_state_symbol, get_game_state, GameState
from modules.player import get_player_avatar
from modules.pokemon_party import get_party
from modules.map import get_map_data_for_current_position
from modules.tasks import is_waiting_for_input, get_global_script_context
from modules.memory import read_symbol
from modules.keyboard import get_naming_screen_data, NamingScreenState


@dataclass
class PlayerState:
    """Player state information"""
    x: int
    y: int
    facing: str  # "Down", "Up", "Left", "Right"
    map_name: str
    map_group: int
    map_number: int
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "position": {"x": self.x, "y": self.y},
            "facing": self.facing,
            "map": self.map_name,
            "map_group": self.map_group,
            "map_number": self.map_number
        }
    
    def __eq__(self, other) -> bool:
        """Check if position/map changed"""
        if not isinstance(other, PlayerState):
            return False
        return (
            self.x == other.x and
            self.y == other.y and
            self.map_name == other.map_name
        )


class MemoryReader:
    """
    Reads game memory and formats it for LLM consumption.
    
    Uses pokebot-gen3's comprehensive memory mapping to extract:
    - Player position and state
    - Current map information
    - Party Pokemon (basic info for now)
    - Movement detection
    """
    
    def __init__(self):
        self.last_state: Optional[PlayerState] = None
    
    def get_player_state(self) -> PlayerState:
        """
        Get current player state.
        
        Returns:
            PlayerState object with position, facing, map, etc.
        """
        avatar = get_player_avatar()
        map_data = get_map_data_for_current_position()
        
        # Determine facing direction string
        # From pokebot-gen3: 1=Down, 2=Up, 3=Left, 4=Right
        facing = avatar.facing_direction
        
        # Extract position from tuple
        x, y = avatar.local_coordinates
        
        state = PlayerState(
            x=x,
            y=y,
            facing=facing,
            map_name=map_data.dict_for_map()["pretty_name"],
            map_group=map_data.map_group,
            map_number=map_data.map_number
        )
        
        return state
    
    def get_current_map_name(self) -> str:
        """
        Get the name of the current map.
        
        Returns:
            Map name string (e.g., "Pallet Town")
        """
        map_data = get_map_data_for_current_position()
        return map_data.dict_for_map()["pretty_name"]
    
    def has_player_moved(self) -> bool:
        """
        Check if player has moved since last check.
        
        Returns:
            True if position or map changed, False otherwise
        """
        current_state = self.get_player_state()
        
        if self.last_state is None:
            # First check, consider it as "moved" to trigger initial processing
            return True
        
        # Check if position or map changed
        moved = current_state != self.last_state
        return moved
    
    def has_map_changed(self) -> bool:
        """
        Check if map has changed since last check.
        
        Returns:
            True if map changed, False otherwise
        """
        current_state = self.get_player_state()
        
        if self.last_state is None:
            return False
        
        # Check only map name
        map_changed = current_state.map_name != self.last_state.map_name
        return map_changed

    def update_last_state(self):
        """Update the stored last state to current state"""
        self.last_state = self.get_player_state()
    
    def get_party_summary(self) -> list[Dict[str, Any]]:
        """
        Get basic party Pokemon information.
        
        Returns:
            List of dicts with basic Pokemon info
        """
        party = get_party()
        party_summary = []
        
        for pokemon in party:
            if pokemon is None:
                continue
            
            # Extract move names
            moves = [move.move.name if move else None for move in pokemon.moves]
            moves = [m for m in moves if m is not None]
            
            party_summary.append({
                "species": pokemon.species.name,
                "level": pokemon.level,
                "hp": {
                    "current": pokemon.current_hp,
                    "max": pokemon.stats.hp
                },
                "moves": moves,
                "is_egg": pokemon.is_egg
            })
        
        return party_summary
    
    def read_full_state(self) -> Dict[str, Any]:
        """
        Read comprehensive game state.
        
        Returns:
            Dictionary with all relevant game state for LLM
        """
        player = self.get_player_state()
        game_state = get_game_state_symbol()
        party_info = self.get_party_summary()
        
        return {
            "player": player.to_dict(),
            "frame": context.frame,
            "game_state": game_state if game_state else "UNKNOWN",
            "party": party_info,
            "party_size": len(party_info)
        }
    
    def get_game_state_type(self) -> str:
        """
        Get current game state type.

        Returns:
            One of: "overworld", "battle", "menu", "naming_screen", "dialogue", "unknown"
        """
        game_state = get_game_state()

        # Check for naming screen first (specific state)
        if game_state == GameState.NAMING_SCREEN:
            return "naming_screen"

        # Check for dialogue (player in overworld but waiting for input)
        # Use our improved is_dialogue_active() which validates script context
        if game_state == GameState.OVERWORLD:
            if self.is_dialogue_active():
                return "dialogue"
            return "overworld"

        if game_state in (GameState.BATTLE, GameState.BATTLE_STARTING, GameState.BATTLE_ENDING):
            return "battle"

        if game_state in (GameState.BAG_MENU, GameState.PARTY_MENU, GameState.POKE_STORAGE,
                          GameState.POKEMON_SUMMARY_SCREEN, GameState.CHOOSE_STARTER):
            return "menu"

        if game_state in (GameState.CHANGE_MAP,):
            return "map_transition"

        return "unknown"

    def is_dialogue_active(self) -> bool:
        """
        Check if dialogue/text box is currently active and waiting for input.

        More robust than just is_waiting_for_input() - also validates that
        there's actually a script running or text printer active.

        Returns:
            True if dialogue is waiting for A/B press
        """
        # First check the standard function
        if not is_waiting_for_input():
            return False

        # Validate that there's actually a script running
        # A stack with just '0x0' means no real script
        script_ctx = get_global_script_context()
        if script_ctx.native_function_name == "WaitForAorBPress":
            # Check if stack is valid (not just null pointers)
            stack = script_ctx.stack
            if not stack or all(s == '0x0' or s == '' for s in stack):
                # No valid stack - this might be a false positive
                # Double-check with text printer state for FRLG
                try:
                    text_printer_data = read_symbol("sTextPrinters", offset=0x1B, size=2)
                    text_printer_is_active = text_printer_data[0]
                    text_printer_state = text_printer_data[1]
                    # States 2 (Clear) and 3 (ScrollStart) mean waiting for button
                    return text_printer_is_active and text_printer_state in (2, 3)
                except:
                    return False

        return True

    def get_naming_screen_info(self) -> Optional[Dict[str, Any]]:
        """
        Get naming screen information if active.

        Returns:
            Dict with naming screen state, or None if not active
        """
        naming_data = get_naming_screen_data()
        if naming_data is None:
            return None

        return {
            "enabled": naming_data.enabled,
            "state": naming_data.state.name,
            "current_input": naming_data.current_input,
            "keyboard_page": naming_data.keyboard_page.name,
            "cursor_position": naming_data.cursor_position,
            "is_ready_for_input": naming_data.state == NamingScreenState.HandleInput
        }

    def read_lightweight_state(self) -> Dict[str, Any]:
        """
        Read lightweight state (without party info).
        Use this for frequent checks.
        
        Returns:
            Dictionary with basic state info
        """
        player = self.get_player_state()
        game_state = get_game_state_symbol()
        
        return {
            "player": player.to_dict(),
            "frame": context.frame,
            "game_state": game_state if game_state else "UNKNOWN"
        }