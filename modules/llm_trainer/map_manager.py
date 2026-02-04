"""Map Manager - Handles map storage, loading, and updates"""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from modules.context import context
from modules.console import console
from modules.llm_trainer.map_graph import MapGraph


class MapManager:
    """
    Manages tile maps and traversal maps for each game area.
    
    Each map area has:
    - tile_map: 2D array of tile names (from vision processor)
    - traversal_map: 2D array of status markers (?, W, N, P, T, I)
    - Pre-allocated coordinate system based on player's max observed position
    - Coordinates match game's coordinate system (not relative)
    
    Maps are stored per map_group/map_number combination.
    """
    
    # Traversal map markers
    UNKNOWN = '?'      # Unexplored
    WALKABLE = 'W'     # Confirmed walkable
    BLOCKED = 'N'      # Non-traversable (wall, obstacle)
    PLAYER = 'P'       # Current player position
    TRAVERSAL = 'T'    # Map transition tile
    INTERACTABLE = 'I' # NPC, sign, or interactable object
    LEDGE = 'L'        # One-way ledge jump
    
    # No buffer - only allocate exactly what's visible
    GRID_BUFFER = 0
    
    def __init__(self):
        self.maps_dir = self._get_maps_directory()
        self.current_map_data: Optional[Dict[str, Any]] = None
        self.current_map_key: Optional[str] = None
        
        # Map connectivity graph
        self.map_graph = MapGraph(self.maps_dir)
        
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
    
    def _ensure_map_size(self, max_x: int, max_y: int, map_data: Optional[Dict[str, Any]] = None):
        """
        Ensure map arrays are large enough to accommodate given coordinates.
        Pre-allocates with buffer for future expansion.
        
        Args:
            max_x: Maximum X coordinate needed
            max_y: Maximum Y coordinate needed
            map_data: Map data (uses current if None)
        """
        if map_data is None:
            map_data = self.current_map_data
        
        if map_data is None:
            return
        
        # Add buffer for future expansion
        target_width = max_x + self.GRID_BUFFER + 1
        target_height = max_y + self.GRID_BUFFER + 1
        
        tile_map = map_data["tile_map"]
        traversal_map = map_data["traversal_map"]
        
        # Expand rows
        while len(tile_map) < target_height:
            tile_map.append([])
            traversal_map.append([])
        
        # Expand columns in each row
        for y in range(target_height):
            # Ensure each row exists
            if y >= len(tile_map):
                tile_map.append([])
            if y >= len(traversal_map):
                traversal_map.append([])
            
            # Expand columns
            while len(tile_map[y]) < target_width:
                tile_map[y].append("unknown")
            while len(traversal_map[y]) < target_width:
                traversal_map[y].append(self.UNKNOWN)
        
        # Update bounds
        bounds = map_data["bounds"]
        bounds["max_x"] = max(bounds["max_x"], max_x)
        bounds["max_y"] = max(bounds["max_y"], max_y)
    
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
        
        # Create new map with empty pre-allocated arrays
        map_data = {
            "map_key": map_key,
            "map_name": map_name,
            "map_group": map_group,
            "map_number": map_number,
            "tile_map": [],      # Will be pre-allocated on first update
            "traversal_map": [], # Will be pre-allocated on first update
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
            console.print("[dim yellow]No map data to save[/]")
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
        
        # Ensure map is large enough
        self._ensure_map_size(x, y, map_data)
        
        # Set the marker
        map_data["traversal_map"][y][x] = marker
    
    def update_tile_map_from_screen(
        self,
        player_x: int,
        player_y: int,
        screen_tiles: List[List[str]],
        map_data: Optional[Dict[str, Any]] = None
    ):
        """
        Update tile map with screen tiles from vision processor.
        Maps screen-relative coordinates to world coordinates.
        
        Important: Screen tiles are 9x15 (after cropping margins).
        Player is at center: row=4, col=7 (0-indexed).
        
        Args:
            player_x: Player world X coordinate
            player_y: Player world Y coordinate
            screen_tiles: 2D array of tile names from vision (9 rows x 15 cols)
            map_data: Map data (uses current if None)
        """
        if map_data is None:
            map_data = self.current_map_data
        
        if map_data is None:
            console.print("[red]No map data to update[/]")
            return
        
        # Screen dimensions from vision processor (9 rows x 15 cols)
        screen_height = len(screen_tiles)
        screen_width = len(screen_tiles[0]) if screen_tiles else 0
        
        if screen_height == 0 or screen_width == 0:
            return
        
        # Player is at center of screen
        player_screen_row = 4  # Center row (0-indexed: 0,1,2,3,4,5,6,7,8)
        player_screen_col = 7  # Center col (0-indexed: 0-14)
        
        # Calculate top-left corner of screen in world coordinates
        screen_top_left_x = player_x - player_screen_col
        screen_top_left_y = player_y - player_screen_row
        
        # Calculate max coordinates we'll need
        max_x = screen_top_left_x + screen_width - 1
        max_y = screen_top_left_y + screen_height - 1
        
        # Ensure map is large enough
        self._ensure_map_size(max_x, max_y, map_data)
        
        tile_map = map_data["tile_map"]
        traversal_map = map_data["traversal_map"]
        
        # Map each screen tile to world coordinates
        for screen_row in range(screen_height):
            for screen_col in range(screen_width):
                world_x = screen_top_left_x + screen_col
                world_y = screen_top_left_y + screen_row

                # Only update non-negative coordinates
                if world_x >= 0 and world_y >= 0:
                    tile_name = screen_tiles[screen_row][screen_col]
                    tile_map[world_y][world_x] = tile_name

        # Mark player position as "player" in tile_map for tracking
        # Vision model sees player sprite as "npc_*", we override it here
        if player_y >= 0 and player_x >= 0:
            tile_map[player_y][player_x] = "player"

    def clear_player_tile(
        self,
        player_x: int,
        player_y: int,
        map_data: Optional[Dict[str, Any]] = None
    ):
        """
        Clear the 'player' marker from tile_map when player leaves the map.
        Infers the actual tile from adjacent tiles.

        Args:
            player_x: Player's last X coordinate
            player_y: Player's last Y coordinate
            map_data: Map data (uses current if None)
        """
        if map_data is None:
            map_data = self.current_map_data

        if map_data is None:
            return

        tile_map = map_data["tile_map"]

        # Check bounds
        if player_y < 0 or player_y >= len(tile_map):
            return
        if player_x < 0 or player_x >= len(tile_map[player_y]):
            return

        # Only clear if it's currently marked as "player"
        if tile_map[player_y][player_x] != "player":
            return

        # Infer the actual tile from adjacent tiles
        inferred_tile = self._infer_tile_from_adjacent(player_x, player_y, tile_map)
        tile_map[player_y][player_x] = inferred_tile

    def _infer_tile_from_adjacent(
        self,
        x: int,
        y: int,
        tile_map: List[List[str]]
    ) -> str:
        """
        Infer what tile should be at (x, y) based on adjacent tiles.

        Args:
            x: X coordinate
            y: Y coordinate
            tile_map: The tile map

        Returns:
            Inferred tile name
        """
        # Check adjacent tiles (up, down, left, right)
        adjacent_positions = [
            (x, y - 1),  # up
            (x, y + 1),  # down
            (x - 1, y),  # left
            (x + 1, y),  # right
        ]

        # Collect valid adjacent tiles (not unknown, not player, not npc_*)
        valid_tiles = []
        for ax, ay in adjacent_positions:
            if ay >= 0 and ay < len(tile_map):
                if ax >= 0 and ax < len(tile_map[ay]):
                    tile = tile_map[ay][ax]
                    # Skip invalid tiles
                    if tile not in ["unknown", "player"] and not tile.startswith("npc"):
                        valid_tiles.append(tile)

        if valid_tiles:
            # Return the most common adjacent tile
            from collections import Counter
            tile_counts = Counter(valid_tiles)
            return tile_counts.most_common(1)[0][0]

        # Fallback to "unknown" if no valid adjacent tiles
        return "unknown"

    def calculate_target_tile(
        self,
        player_x: int,
        player_y: int,
        direction: str
    ) -> Tuple[int, int]:
        """
        Calculate the tile coordinates in the given direction from player.
        
        Args:
            player_x: Player X coordinate
            player_y: Player Y coordinate
            direction: Direction ("Up", "Down", "Left", "Right")
            
        Returns:
            (target_x, target_y) tuple
        """
        if direction == "Up":
            return (player_x, player_y - 1)
        elif direction == "Down":
            return (player_x, player_y + 1)
        elif direction == "Left":
            return (player_x - 1, player_y)
        elif direction == "Right":
            return (player_x + 1, player_y)
        else:
            # Unknown direction, return same position
            console.print(f"[yellow]Warning: Unknown direction '{direction}'[/]")
            return (player_x, player_y)
    
    def get_traversal_view(
        self,
        player_x: int,
        player_y: int,
        radius: int = 4,
        map_data: Optional[Dict[str, Any]] = None
    ) -> List[List[str]]:
        """
        Get a view of the traversal map centered on the player.

        Args:
            player_x: Player world X coordinate
            player_y: Player world Y coordinate
            radius: How many tiles in each direction (default 4 = 9x9 grid)
            map_data: Map data (uses current if None)

        Returns:
            2D array of traversal markers, player at center
        """
        if map_data is None:
            map_data = self.current_map_data

        view = []
        for dy in range(-radius, radius + 1):
            row = []
            for dx in range(-radius, radius + 1):
                world_x = player_x + dx
                world_y = player_y + dy
                marker = self.get_traversal_at(world_x, world_y, map_data)
                row.append(marker)
            view.append(row)

        return view

    def get_tile_view(
        self,
        player_x: int,
        player_y: int,
        radius: int = 4,
        map_data: Optional[Dict[str, Any]] = None
    ) -> List[List[str]]:
        """
        Get a view of the tile map centered on the player.

        Args:
            player_x: Player world X coordinate
            player_y: Player world Y coordinate
            radius: How many tiles in each direction (default 4 = 9x9 grid)
            map_data: Map data (uses current if None)

        Returns:
            2D array of tile names, player at center
        """
        if map_data is None:
            map_data = self.current_map_data

        view = []
        for dy in range(-radius, radius + 1):
            row = []
            for dx in range(-radius, radius + 1):
                world_x = player_x + dx
                world_y = player_y + dy
                tile = self.get_tile_at(world_x, world_y, map_data)
                row.append(tile if tile else "unknown")
            view.append(row)

        return view

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
        tiles_walkable = 0
        tiles_blocked = 0

        # Count tile types
        for row in map_data["traversal_map"]:
            for marker in row:
                if marker != self.UNKNOWN:
                    tiles_explored += 1
                if marker == self.WALKABLE or marker == self.PLAYER:
                    tiles_walkable += 1
                elif marker == self.BLOCKED:
                    tiles_blocked += 1

        return (
            f"{map_data['map_name']} | "
            f"Bounds: ({bounds['min_x']},{bounds['min_y']}) to ({bounds['max_x']},{bounds['max_y']}) | "
            f"Explored: {tiles_explored} ({tiles_walkable}W, {tiles_blocked}N) | "
            f"Visits: {map_data['visit_count']}"
        )

    def handle_map_transition(
        self,
        old_map_key: str,
        old_position: Tuple[int, int],
        old_facing: str,
        new_map_key: str,
        new_position: Tuple[int, int],
        new_facing: str
    ):
        """
        Handle a map transition by creating/updating connection.

        Args:
            old_map_key: Previous map key
            old_position: Exit tile position
            old_facing: Direction player was facing when exiting
            new_map_key: New map key
            new_position: Entry tile position in new map
            new_facing: Direction player is facing after entering
        """
        exit_tile = old_position

        # Entry tile: one tile back from where the player appeared
        reverse_dir = {
            "Up": "Down",
            "Down": "Up",
            "Left": "Right",
            "Right": "Left"
        }.get(new_facing, new_facing)

        entry_tile_x, entry_tile_y = self.calculate_target_tile(
            new_position[0],
            new_position[1],
            reverse_dir
        )
        entry_tile = (entry_tile_x, entry_tile_y)

        self.map_graph.add_connection(
            old_map_key,
            exit_tile,
            new_map_key,
            entry_tile,
            old_facing
        )

        console.print(
            f"[magenta]Added connection: "
            f"{old_map_key} {exit_tile} → {new_map_key} {entry_tile}[/]"
        )