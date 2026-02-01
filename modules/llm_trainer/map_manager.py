"""Map Manager - Handles map storage, loading, and updates"""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from modules.context import context
from modules.console import console


class MapManager:
    """
    Manages tile maps and traversal maps for each game area.
    
    Each map area has:
    - tile_map: 2D array of tile names (from vision processor)
    - traversal_map: 2D array of status markers (?, W, N, P, T, I)
    - Coordinate system starting at (0, 0) for each map
    - Links to other maps via traversal tiles (T)
    
    Maps are stored per map_group/map_number combination.
    """
    
    # Traversal map markers
    UNKNOWN = '?'      # Unexplored
    WALKABLE = 'W'     # Confirmed walkable
    BLOCKED = 'N'      # Non-traversable (wall, obstacle)
    PLAYER = 'P'       # Current player position
    TRAVERSAL = 'T'    # Map transition tile
    INTERACTABLE = 'I' # NPC, sign, or interactable object
    
    def __init__(self):
        self.maps_dir = self._get_maps_directory()
        self.current_map_data: Optional[Dict[str, Any]] = None
        self.current_map_key: Optional[str] = None
        
        # Map connectivity graph (will build in Phase 6C)
        self.map_connections: Dict[str, List[Dict[str, Any]]] = {}
        
        console.print(f"[yellow]Map Manager initialized. Maps directory: {self.maps_dir}[/]")
    
    def _get_maps_directory(self) -> Path:
        """Get or create the maps directory for current profile"""
        maps_dir = Path(context.profile.path) / "llm_trainer" / "maps"
        maps_dir.mkdir(parents=True, exist_ok=True)
        return maps_dir
    
    def _get_map_key(self, map_group: int, map_number: int) -> str:
        """Generate unique key for a map"""
        return f"map_{map_group}_{map_number}"
    
    def _get_map_filepath(self, map_key: str) -> Path:
        """Get filepath for a map's JSON file"""
        return self.maps_dir / f"{map_key}.json"
    
    def load_map(self, map_name: str, map_group: int, map_number: int) -> Dict[str, Any]:
        """
        Load a map from disk, or create new if doesn't exist.
        
        Args:
            map_name: Human-readable map name
            map_group: Map group number
            map_number: Map number within group
            
        Returns:
            Map data dictionary
        """
        map_key = self._get_map_key(map_group, map_number)
        filepath = self._get_map_filepath(map_key)
        
        # Try to load existing map
        if filepath.exists():
            try:
                with open(filepath, 'r') as f:
                    map_data = json.load(f)
                console.print(f"[cyan]Loaded map: {map_name} ({map_key})[/]")
                self.current_map_data = map_data
                self.current_map_key = map_key
                return map_data
            except Exception as e:
                console.print(f"[red]Error loading map {map_key}: {e}[/]")
                # Fall through to create new map
        
        # Create new map
        map_data = {
            "map_key": map_key,
            "map_name": map_name,
            "map_group": map_group,
            "map_number": map_number,
            "tile_map": [],      # 2D array of tile names
            "traversal_map": [], # 2D array of status markers
            "created_at": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat(),
            "visit_count": 0,
            "bounds": {
                "min_x": 0,
                "min_y": 0,
                "max_x": 0,
                "max_y": 0
            }
        }
        
        console.print(f"[green]Created new map: {map_name} ({map_key})[/]")
        self.current_map_data = map_data
        self.current_map_key = map_key
        return map_data
    
    def save_map(self, map_data: Optional[Dict[str, Any]] = None):
        """
        Save map data to disk.
        
        Args:
            map_data: Map data to save (uses current if None)
        """
        if map_data is None:
            map_data = self.current_map_data
        
        if map_data is None:
            console.print("[red]No map data to save[/]")
            return
        
        map_key = map_data["map_key"]
        filepath = self._get_map_filepath(map_key)
        
        # Update timestamp
        map_data["last_updated"] = datetime.now().isoformat()
        
        try:
            with open(filepath, 'w') as f:
                json.dump(map_data, f, indent=2)
            console.print(f"[dim green]Saved map: {map_key}[/]")
        except Exception as e:
            console.print(f"[red]Error saving map {map_key}: {e}[/]")
    
    def get_tile_at(self, x: int, y: int, map_data: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """
        Get tile name at world coordinates.
        
        Args:
            x: X coordinate
            y: Y coordinate
            map_data: Map data (uses current if None)
            
        Returns:
            Tile name or None if out of bounds
        """
        if map_data is None:
            map_data = self.current_map_data
        
        if map_data is None or not map_data["tile_map"]:
            return None
        
        tile_map = map_data["tile_map"]
        
        # Check bounds
        if y < 0 or y >= len(tile_map):
            return None
        if x < 0 or x >= len(tile_map[y]):
            return None
        
        return tile_map[y][x]
    
    def get_traversal_at(self, x: int, y: int, map_data: Optional[Dict[str, Any]] = None) -> str:
        """
        Get traversal marker at world coordinates.
        
        Args:
            x: X coordinate
            y: Y coordinate
            map_data: Map data (uses current if None)
            
        Returns:
            Traversal marker (defaults to '?' if unknown)
        """
        if map_data is None:
            map_data = self.current_map_data
        
        if map_data is None or not map_data["traversal_map"]:
            return self.UNKNOWN
        
        traversal_map = map_data["traversal_map"]
        
        # Check bounds
        if y < 0 or y >= len(traversal_map):
            return self.UNKNOWN
        if x < 0 or x >= len(traversal_map[y]):
            return self.UNKNOWN
        
        return traversal_map[y][x]
    
    def set_traversal_at(self, x: int, y: int, marker: str, map_data: Optional[Dict[str, Any]] = None):
        """
        Set traversal marker at world coordinates.
        Expands map if necessary.
        
        Args:
            x: X coordinate
            y: Y coordinate
            marker: Traversal marker to set
            map_data: Map data (uses current if None)
        """
        if map_data is None:
            map_data = self.current_map_data
        
        if map_data is None:
            console.print("[red]No map data to update[/]")
            return
        
        # Ensure traversal_map is large enough
        traversal_map = map_data["traversal_map"]
        
        # Expand rows if needed
        while len(traversal_map) <= y:
            traversal_map.append([])
        
        # Expand columns if needed
        while len(traversal_map[y]) <= x:
            traversal_map[y].append(self.UNKNOWN)
        
        # Set the marker
        traversal_map[y][x] = marker
        
        # Update bounds
        bounds = map_data["bounds"]
        bounds["max_x"] = max(bounds["max_x"], x)
        bounds["max_y"] = max(bounds["max_y"], y)
    
    def update_tile_map(
        self,
        player_x: int,
        player_y: int,
        screen_tiles: List[List[str]],
        map_data: Optional[Dict[str, Any]] = None
    ):
        """
        Update tile map with new screen tiles centered on player.
        
        Args:
            player_x: Player world X coordinate
            player_y: Player world Y coordinate
            screen_tiles: 2D array of tile names from vision processor
            map_data: Map data (uses current if None)
        """
        if map_data is None:
            map_data = self.current_map_data
        
        if map_data is None:
            console.print("[red]No map data to update[/]")
            return
        
        tile_map = map_data["tile_map"]
        
        # Screen dimensions (from vision processor)
        screen_height = len(screen_tiles)
        screen_width = len(screen_tiles[0]) if screen_tiles else 0
        
        # Calculate top-left corner of screen in world coordinates
        # Player is at center of screen
        top_left_x = player_x - (screen_width // 2)
        top_left_y = player_y - (screen_height // 2)
        
        # Update tile map
        for screen_y in range(screen_height):
            for screen_x in range(screen_width):
                world_x = top_left_x + screen_x
                world_y = top_left_y + screen_y
                
                # Skip negative coordinates
                if world_x < 0 or world_y < 0:
                    continue
                
                # Expand tile_map if needed
                while len(tile_map) <= world_y:
                    tile_map.append([])
                
                while len(tile_map[world_y]) <= world_x:
                    tile_map[world_y].append("unknown")
                
                # Set tile
                tile_name = screen_tiles[screen_y][screen_x]
                tile_map[world_y][world_x] = tile_name
        
        # Update bounds
        bounds = map_data["bounds"]
        bounds["max_x"] = max(bounds["max_x"], player_x + (screen_width // 2))
        bounds["max_y"] = max(bounds["max_y"], player_y + (screen_height // 2))
    
    def calculate_target_tile(
        self,
        player_x: int,
        player_y: int,
        facing: str
    ) -> Tuple[int, int]:
        """
        Calculate the tile the player would move to if they walked forward.
        
        Args:
            player_x: Player X coordinate
            player_y: Player Y coordinate
            facing: Direction player is facing ("Up", "Down", "Left", "Right")
            
        Returns:
            (target_x, target_y) tuple
        """
        if facing == "Up":
            return (player_x, player_y - 1)
        elif facing == "Down":
            return (player_x, player_y + 1)
        elif facing == "Left":
            return (player_x - 1, player_y)
        elif facing == "Right":
            return (player_x + 1, player_y)
        else:
            # Unknown facing, return same position
            return (player_x, player_y)
    
    def get_map_summary(self, map_data: Optional[Dict[str, Any]] = None) -> str:
        """
        Get a summary string of the map.
        
        Args:
            map_data: Map data (uses current if None)
            
        Returns:
            Summary string
        """
        if map_data is None:
            map_data = self.current_map_data
        
        if map_data is None:
            return "No map loaded"
        
        bounds = map_data["bounds"]
        tiles_explored = 0
        
        # Count explored tiles
        for row in map_data["traversal_map"]:
            for marker in row:
                if marker != self.UNKNOWN:
                    tiles_explored += 1
        
        return (
            f"{map_data['map_name']} | "
            f"Bounds: ({bounds['min_x']},{bounds['min_y']}) to ({bounds['max_x']},{bounds['max_y']}) | "
            f"Explored: {tiles_explored} tiles | "
            f"Visits: {map_data['visit_count']}"
        )