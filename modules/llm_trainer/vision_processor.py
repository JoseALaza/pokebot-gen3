"""Vision Processor - Converts screenshots to tile representations"""

import numpy as np
from typing import List, Dict, Any, Optional
from modules.context import context
from modules.console import console


class VisionProcessor:
    """
    Processes game screenshots into tile-based representations.
    
    Flow:
    1. Get screenshot from emulator (PIL Image)
    2. Convert to NumPy array
    3. Split into tiles (16x16 pixels)
    4. Classify each tile (using ResNet model - TODO)
    5. Generate tile map and traversal map
    
    For now, uses placeholder classification based on color.
    ResNet model integration coming in future phase.
    """
    
    TILE_SIZE = 16  # Pokemon Gen3 uses 16x16 tiles
    SCREEN_WIDTH = 240
    SCREEN_HEIGHT = 160
    
    def __init__(self):
        self.tile_classifier = None  # TODO: Load ResNet model later
        self.tiles_x = self.SCREEN_WIDTH // self.TILE_SIZE   # 15 tiles
        self.tiles_y = self.SCREEN_HEIGHT // self.TILE_SIZE  # 10 tiles
        
        # Cache for last processed frame
        self.last_screenshot: Optional[np.ndarray] = None
        self.last_tile_map: Optional[List[List[str]]] = None
        
        console.print(
            f"[yellow]Vision processor initialized: "
            f"{self.tiles_x}x{self.tiles_y} tiles "
            f"(ResNet model not loaded yet)[/]"
        )
    
    def get_screenshot(self) -> np.ndarray:
        """
        Get current frame from emulator as numpy array.
        
        Returns:
            Numpy array of shape (160, 240, 3) with RGB values
        """
        # Get PIL Image from emulator (already in RGB format)
        pil_image = context.emulator.get_screenshot()
        
        # Convert PIL Image to NumPy array
        screenshot = np.array(pil_image)
        
        # Verify shape is correct (should be 160x240x3)
        if screenshot.shape != (self.SCREEN_HEIGHT, self.SCREEN_WIDTH, 3):
            console.print(
                f"[red]Warning: Unexpected screenshot shape {screenshot.shape}, "
                f"expected ({self.SCREEN_HEIGHT}, {self.SCREEN_WIDTH}, 3)[/]"
            )
        
        # Cache the screenshot
        self.last_screenshot = screenshot.copy()
        
        return screenshot
    
    def split_into_tiles(self, screenshot: np.ndarray) -> List[List[np.ndarray]]:
        """
        Split screenshot into 16x16 pixel tiles.
        
        Args:
            screenshot: Full screenshot array (160, 240, 3)
            
        Returns:
            2D list of tile arrays, each of shape (16, 16, 3)
            Dimensions: [y][x] where y=0-9, x=0-14
        """
        tiles = []
        
        for y in range(self.tiles_y):
            row = []
            for x in range(self.tiles_x):
                y_start = y * self.TILE_SIZE
                y_end = y_start + self.TILE_SIZE
                x_start = x * self.TILE_SIZE
                x_end = x_start + self.TILE_SIZE
                
                tile = screenshot[y_start:y_end, x_start:x_end]
                row.append(tile)
            tiles.append(row)
        
        return tiles
    
    def classify_tile_placeholder(self, tile: np.ndarray) -> str:
        """
        Placeholder tile classifier based on average color.
        
        This will be replaced with ResNet model classification.
        
        Args:
            tile: 16x16x3 numpy array
            
        Returns:
            Tile class name (placeholder labels)
        """
        # Calculate average color intensity
        avg_color = tile.mean()
        
        # Calculate color variance (to distinguish solid colors from textures)
        variance = tile.std()
        
        # Simple heuristic classification
        if avg_color < 30:
            return "black"
        elif avg_color < 60:
            return "dark_tile"
        elif avg_color > 200 and variance < 20:
            return "white"
        elif variance < 15:
            # Low variance = solid color
            if avg_color < 100:
                return "wall"
            else:
                return "floor_tile"
        else:
            # High variance = textured
            return "unknown"
    
    def classify_tile(self, tile: np.ndarray) -> str:
        """
        Classify a single tile.
        
        Args:
            tile: 16x16x3 numpy array
            
        Returns:
            Tile class name (e.g., "floor_tile", "wall", "player_left")
        """
        if self.tile_classifier is None:
            # Use placeholder until ResNet model is loaded
            return self.classify_tile_placeholder(tile)
        
        # TODO: Use actual ResNet model
        # prediction = self.tile_classifier.predict(tile)
        # return prediction
        
        return "unknown"
    
    def generate_tile_map(self, tiles: List[List[np.ndarray]]) -> List[List[str]]:
        """
        Generate tile map by classifying each tile.
        
        Args:
            tiles: 2D list of tile arrays
            
        Returns:
            2D list of tile class names
        """
        tile_map = []
        
        for row in tiles:
            tile_row = []
            for tile in row:
                classification = self.classify_tile(tile)
                tile_row.append(classification)
            tile_map.append(tile_row)
        
        return tile_map
    
    def generate_traversal_map(self, tile_map: List[List[str]]) -> List[List[str]]:
        """
        Generate traversal map based on tile classifications.
        
        Args:
            tile_map: 2D list of tile class names
            
        Returns:
            2D list with traversal markers:
            - 'N' = Non-traversable (walls, obstacles)
            - '?' = Unknown/potentially traversable
            - 'P' = Player position (TODO: detect player tile)
        """
        traversal_map = []
        
        # Non-traversable tile types (expand as needed)
        non_traversable = {"black", "wall", "white"}
        
        for row in tile_map:
            trav_row = []
            for tile_class in row:
                if tile_class in non_traversable:
                    trav_row.append('N')
                elif tile_class == "player_left" or tile_class == "player_right" or \
                     tile_class == "player_up" or tile_class == "player_down":
                    trav_row.append('P')
                else:
                    trav_row.append('?')
            traversal_map.append(trav_row)
        
        return traversal_map
    
    def tile_map_to_string(self, tile_map: List[List[str]]) -> str:
        """
        Convert tile map to string representation.
        
        Args:
            tile_map: 2D list of tile class names
            
        Returns:
            String with space-separated tiles, one row per line
        """
        return '\n'.join([' '.join(row) for row in tile_map])
    
    def traversal_map_to_string(self, traversal_map: List[List[str]]) -> str:
        """
        Convert traversal map to string representation.
        
        Args:
            traversal_map: 2D list of traversal markers
            
        Returns:
            String with space-separated markers, one row per line
        """
        return '\n'.join([' '.join(row) for row in traversal_map])
    
    def process_frame(self) -> Dict[str, Any]:
        """
        Process current frame into tile representation.
        
        Returns:
            Dictionary with tile_map, traversal_map, and metadata
        """
        # 1. Get screenshot (PIL → NumPy)
        screenshot = self.get_screenshot()
        
        # 2. Split into tiles
        tiles = self.split_into_tiles(screenshot)
        
        # 3. Classify tiles
        tile_map = self.generate_tile_map(tiles)
        
        # 4. Generate traversal map
        traversal_map = self.generate_traversal_map(tile_map)
        
        # Cache results
        self.last_tile_map = tile_map
        
        return {
            "tile_map": tile_map,
            "tile_map_string": self.tile_map_to_string(tile_map),
            "traversal_map": traversal_map,
            "traversal_map_string": self.traversal_map_to_string(traversal_map),
            "tiles_x": self.tiles_x,
            "tiles_y": self.tiles_y,
            "screen_size": {
                "width": self.SCREEN_WIDTH,
                "height": self.SCREEN_HEIGHT
            }
        }
    
    def get_tile_statistics(self, tile_map: List[List[str]]) -> Dict[str, int]:
        """
        Get statistics about tile classifications.
        
        Args:
            tile_map: 2D list of tile class names
            
        Returns:
            Dictionary with counts of each tile type
        """
        stats = {}
        
        for row in tile_map:
            for tile_class in row:
                stats[tile_class] = stats.get(tile_class, 0) + 1
        
        return stats
    
    def get_debug_info(self) -> Dict[str, Any]:
        """
        Get debug information about the last processed frame.
        
        Returns:
            Dictionary with debug info about screenshot and tiles
        """
        debug_info = {
            "screenshot_captured": self.last_screenshot is not None,
            "screenshot_shape": self.last_screenshot.shape if self.last_screenshot is not None else None,
            "screenshot_dtype": str(self.last_screenshot.dtype) if self.last_screenshot is not None else None,
            "screenshot_min_value": int(self.last_screenshot.min()) if self.last_screenshot is not None else None,
            "screenshot_max_value": int(self.last_screenshot.max()) if self.last_screenshot is not None else None,
            "screenshot_mean_value": float(self.last_screenshot.mean()) if self.last_screenshot is not None else None,
            "last_tile_map_exists": self.last_tile_map is not None,
            "last_tile_map_dimensions": (len(self.last_tile_map), len(self.last_tile_map[0])) if self.last_tile_map else None
        }
        
        return debug_info