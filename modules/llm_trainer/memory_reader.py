"""Memory Reader - Extracts game state for LLM consumption"""

from dataclasses import dataclass
from typing import Optional, Dict, Any
from modules.context import context
from modules.memory import get_game_state, GameState
from modules.player import get_player_avatar
from modules.pokemon import get_party


@dataclass
class PlayerState:
    """Player state information"""
    x: int
    y: int
    facing: str  # "UP", "DOWN", "LEFT", "RIGHT"
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
        self._frame_count = 0
    
    def get_player_state(self) -> PlayerState:
        """
        Get current player state.
        
        Returns:
            PlayerState object with position, facing, map, etc.
        """
        avatar = get_player_avatar()
        game_state = get_game_state()
        
        # Determine facing direction
        # From pokebot-gen3: 1=DOWN, 2=UP, 3=LEFT, 4=RIGHT
        facing_map = {
            1: "DOWN",
            2: "UP",
            3: "LEFT",
            4: "RIGHT"
        }
        facing = facing_map.get(avatar.facing_direction, "UNKNOWN")
        
        state = PlayerState(
            x=avatar.local_coordinates.x,
            y=avatar.local_coordinates.y,
            facing=facing,
            map_name=game_state.map.name,
            map_group=game_state.map.map_group,
            map_number=game_state.map.map_number
        )
        
        return state
    
    def get_current_map_name(self) -> str:
        """Get the name of the current map"""
        return get_game_state().map.name
    
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
        
        moved = current_state != self.last_state
        return moved
    
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
            
            # Get move names
            moves = [move.move.name if move else None for move in pokemon.moves]
            moves = [m for m in moves if m is not None]  # Filter out None
            
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
        game_state = get_game_state()
        
        # Get party info (can be expensive, so only call when needed)
        party_info = self.get_party_summary()
        
        state = {
            "player": player.to_dict(),
            "frame": context.frame,
            "game_state": game_state.value.name if game_state else "UNKNOWN",
            "party": party_info,
            "party_size": len(party_info)
        }
        
        return state
    
    def read_lightweight_state(self) -> Dict[str, Any]:
        """
        Read lightweight state (without party info).
        Use this for frequent checks.
        
        Returns:
            Dictionary with basic state info
        """
        player = self.get_player_state()
        game_state = get_game_state()
        
        return {
            "player": player.to_dict(),
            "frame": context.frame,
            "game_state": game_state.value.name if game_state else "UNKNOWN"
        }