"""Vision Processor - Converts screenshots to tile representations using ResNet"""

import numpy as np
import torch
import torch.nn.functional as F
from torchvision import models
from pathlib import Path
from typing import List, Dict, Any, Optional
from modules.context import context
from modules.console import console


class VisionProcessor:
    """
    Processes game screenshots into tile-based representations using ResNet-18.
    
    Flow:
    1. Get screenshot from emulator (PIL Image, 240x160)
    2. Crop margins (top 8px, bottom 8px)
    3. Split into 16x16 tiles (15 cols x 9 rows = 135 tiles)
    4. Batch upscale tiles to 640x640 using nearest-neighbor
    5. Run ResNet inference to classify each tile
    6. Return tile map with class names
    """
    
    TILE_SIZE = 16
    SCREEN_WIDTH = 240
    SCREEN_HEIGHT = 160
    CROP_TOP = 8
    CROP_BOTTOM = 8
    UPSCALE_SIZE = 640
    NUM_CLASSES = 103
    
    def __init__(self):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = None
        self.class_labels = []
        
        # Calculate grid dimensions after cropping
        cropped_height = self.SCREEN_HEIGHT - self.CROP_TOP - self.CROP_BOTTOM  # 144
        self.tiles_y = cropped_height // self.TILE_SIZE  # 9 rows
        self.tiles_x = self.SCREEN_WIDTH // self.TILE_SIZE  # 15 cols
        
        # Cache for last processed frame
        self.last_screenshot: Optional[np.ndarray] = None
        self.last_tile_map: Optional[List[List[str]]] = None
        
        # Try to load ResNet model
        self._load_model()
        
        if self.model is not None:
            console.print(
                f"[green]Vision processor initialized: "
                f"{self.tiles_x}x{self.tiles_y} tiles, "
                f"ResNet-18 loaded on {self.device}[/]"
            )
        else:
            console.print(
                f"[yellow]Vision processor initialized: "
                f"{self.tiles_x}x{self.tiles_y} tiles, "
                f"ResNet model NOT loaded (using placeholders)[/]"
            )
    
    def _load_model(self):
        """Load ResNet-18 model with trained weights"""
        try:
            # Load class labels
            labels_path = Path(__file__).parent / "models" / "class_labels_run2.txt"
            if not labels_path.exists():
                console.print(f"[red]Class labels not found at {labels_path}[/]")
                return
            
            with open(labels_path, 'r') as f:
                self.class_labels = [line.strip() for line in f.readlines()]
            
            if len(self.class_labels) != self.NUM_CLASSES:
                console.print(
                    f"[red]Expected {self.NUM_CLASSES} classes, "
                    f"found {len(self.class_labels)}[/]"
                )
                return
            
            # Load model architecture
            self.model = models.resnet18(weights=None)  # No pretrained weights
            self.model.fc = torch.nn.Linear(self.model.fc.in_features, self.NUM_CLASSES)
            
            # Load trained weights
            model_path = Path(__file__).parent / "models" / "best_resnet.pth"
            if not model_path.exists():
                console.print(f"[yellow]Model weights not found at {model_path}[/]")
                console.print("[yellow]Download from: https://drive.google.com/file/d/1rGlGfUp_i34QMNzXRiSvOVYFtMTdV77M/view?usp=sharing[/]")
                console.print(f"[yellow]Place in: {model_path.parent}/[/]")
                self.model = None
                return
            
            state_dict = torch.load(model_path, map_location=self.device)
            self.model.load_state_dict(state_dict)
            self.model.to(self.device)
            self.model.eval()
            
            console.print(f"[green]ResNet-18 model loaded successfully ({len(self.class_labels)} classes)[/]")
            
        except Exception as e:
            console.print(f"[red]Error loading ResNet model: {e}[/]")
            self.model = None
    
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
        
        # Verify shape
        if screenshot.shape != (self.SCREEN_HEIGHT, self.SCREEN_WIDTH, 3):
            console.print(
                f"[red]Warning: Unexpected screenshot shape {screenshot.shape}, "
                f"expected ({self.SCREEN_HEIGHT}, {self.SCREEN_WIDTH}, 3)[/]"
            )
        
        # Cache the screenshot
        self.last_screenshot = screenshot.copy()
        
        return screenshot
    
    def crop_screenshot(self, screenshot: np.ndarray) -> np.ndarray:
        """
        Crop top and bottom margins from screenshot.
        
        Args:
            screenshot: Full screenshot (160, 240, 3)
            
        Returns:
            Cropped screenshot (144, 240, 3)
        """
        # Crop top 8px and bottom 8px
        cropped = screenshot[self.CROP_TOP:-self.CROP_BOTTOM, :, :]
        return cropped
    
    def extract_tiles(self, screenshot: np.ndarray) -> np.ndarray:
        """
        Extract 16x16 tiles from screenshot using NumPy slicing.
        
        Args:
            screenshot: Cropped screenshot (144, 240, 3)
            
        Returns:
            Array of tiles with shape (135, 16, 16, 3)
        """
        tiles = []
        
        for row in range(self.tiles_y):
            for col in range(self.tiles_x):
                y_start = row * self.TILE_SIZE
                y_end = y_start + self.TILE_SIZE
                x_start = col * self.TILE_SIZE
                x_end = x_start + self.TILE_SIZE
                
                tile = screenshot[y_start:y_end, x_start:x_end, :]
                tiles.append(tile)
        
        # Stack into single array: (135, 16, 16, 3)
        tiles_array = np.stack(tiles)
        return tiles_array
    
    def classify_tiles_resnet(self, tiles: np.ndarray) -> List[List[str]]:
        """
        Classify tiles using ResNet model (batch inference).
        
        Args:
            tiles: Array of tiles (135, 16, 16, 3)
            
        Returns:
            2D list of tile class names (9 rows x 15 cols)
        """
        if self.model is None:
            # Fallback to placeholder classification
            return self.classify_tiles_placeholder(tiles)
        
        try:
            # Convert to tensor: (135, 16, 16, 3) -> (135, 3, 16, 16)
            tiles_tensor = torch.from_numpy(tiles).permute(0, 3, 1, 2).float() / 255.0
            
            # Batch upscale to 640x640 using nearest-neighbor
            upscaled_tiles = F.interpolate(
                tiles_tensor,
                size=(self.UPSCALE_SIZE, self.UPSCALE_SIZE),
                mode='nearest'
            )
            
            # Move to device
            upscaled_tiles = upscaled_tiles.to(self.device)
            
            # Run inference
            with torch.no_grad():
                outputs = self.model(upscaled_tiles)
                probs = torch.nn.functional.softmax(outputs, dim=1)
                predictions = torch.argmax(probs, dim=1)  # Take top-1 prediction
            
            # Convert predictions to class names
            predictions_cpu = predictions.cpu().numpy()
            tile_classes = [self.class_labels[idx] for idx in predictions_cpu]
            
            # Reshape to 2D grid (9 rows x 15 cols)
            tile_map = []
            for row in range(self.tiles_y):
                tile_row = []
                for col in range(self.tiles_x):
                    idx = row * self.tiles_x + col
                    tile_row.append(tile_classes[idx])
                tile_map.append(tile_row)
            
            return tile_map
            
        except Exception as e:
            console.print(f"[red]Error during ResNet inference: {e}[/]")
            return self.classify_tiles_placeholder(tiles)
    
    def classify_tiles_placeholder(self, tiles: np.ndarray) -> List[List[str]]:
        """
        Placeholder classifier based on color (fallback when ResNet not available).
        
        Args:
            tiles: Array of tiles (135, 16, 16, 3)
            
        Returns:
            2D list of placeholder tile names (9 rows x 15 cols)
        """
        tile_map = []
        
        for row in range(self.tiles_y):
            tile_row = []
            for col in range(self.tiles_x):
                idx = row * self.tiles_x + col
                tile = tiles[idx]
                
                # Simple color-based classification
                avg_color = tile.mean()
                variance = tile.std()
                
                if avg_color < 30:
                    tile_name = "black"
                elif avg_color < 60:
                    tile_name = "dark_tile"
                elif avg_color > 200 and variance < 20:
                    tile_name = "white"
                elif variance < 15:
                    if avg_color < 100:
                        tile_name = "wall"
                    else:
                        tile_name = "floor_tile"
                else:
                    tile_name = "unknown"
                
                tile_row.append(tile_name)
            tile_map.append(tile_row)
        
        return tile_map
    
    def generate_traversal_map(self, tile_map: List[List[str]]) -> List[List[str]]:
        """
        Generate initial traversal map based on tile classifications.
        
        All tiles start as '?' (unknown). This is just initialization - 
        actual traversability is determined by movement attempts.
        
        Args:
            tile_map: 2D list of tile class names
            
        Returns:
            2D list with traversal markers (all '?' initially)
        """
        traversal_map = []
        
        for row in tile_map:
            trav_row = ['?' for _ in row]
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
        # 1. Get screenshot (240x160x3)
        screenshot = self.get_screenshot()
        
        # 2. Crop margins (144x240x3)
        cropped = self.crop_screenshot(screenshot)
        
        # 3. Extract tiles (135, 16, 16, 3)
        tiles = self.extract_tiles(cropped)
        
        # 4. Classify tiles using ResNet (9x15 grid of class names)
        tile_map = self.classify_tiles_resnet(tiles)
        
        # 5. Generate initial traversal map (9x15 grid of '?')
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