import torch
import torch.nn.functional as F
import torchvision.transforms as transforms
from torchvision import models
from PIL import Image
import os
import time
import numpy as np
import logging
from pathlib import Path

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class ResNetVisionTool:
    """
    Handles screenshot processing and ResNet-based tile predictions.
    
    Future Optimization Note:
    Implement scrolling optimizations to only process newly visible tiles.
    """
    def __init__(self, model_path, debug_mode=False):
        """Load ResNet model and initialize preprocessing pipeline."""
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = models.resnet18()
        self.model.fc = torch.nn.Linear(self.model.fc.in_features, 103)  # 103 classes
        self.model.load_state_dict(torch.load(model_path, map_location=self.device))
        self.model.to(self.device)
        self.model.eval()
        self.class_labels = self._load_class_names()

        # We still have a basic transform for legacy purposes if needed
        self.transform = transforms.Compose([
            transforms.Resize((640, 640)),
            transforms.ToTensor(),
        ])

        # Debug mode: Save processed tiles only if True
        self.debug_mode = debug_mode
        self.debug_dir = Path("debug_tiles")
        if self.debug_mode:
            self.debug_dir.mkdir(exist_ok=True)

    def process_image(self, image_path):
        """
        Processes an image, splits it into tiles using NumPy slicing,
        upscales them in one batch, and returns the top-3 predictions for each tile.
        """
        overall_start = time.time()

        # Step 1: Load and crop the image
        load_start = time.time()
        img = Image.open(image_path).convert("RGB")
        width, height = img.size
        # Crop top and bottom margins (assumed fixed 8 pixels each)
        img = img.crop((0, 8, width, height - 8))
        load_end = time.time()
        logger.debug(f"Image loaded and cropped in {load_end - load_start:.2f} seconds")

        # Step 2: Convert image to NumPy array and extract tiles via slicing
        extraction_start = time.time()
        img_np = np.array(img)  # shape: (H, W, 3)
        tile_size = 16
        tiles_np_list = []   # List to hold each tile as a NumPy array
        tile_positions = []  # Corresponding (row, col) positions
        for row in range(9):
            for col in range(15):
                left = col * tile_size
                upper = row * tile_size
                tile_np = img_np[upper:upper+tile_size, left:left+tile_size, :]
                tiles_np_list.append(tile_np)
                tile_positions.append((row, col))
        extraction_end = time.time()
        logger.debug(f"Tiles extracted via NumPy slicing in {extraction_end - extraction_start:.2f} seconds")

        # Step 3: Batch conversion & upscale all tiles at once
        preprocess_start = time.time()
        # Convert list of tiles to a tensor; shape becomes (N, H, W, C)
        tiles_tensor = torch.tensor(np.stack(tiles_np_list))  # (135, 16, 16, 3)
        # Rearrange to (N, C, H, W) and convert to float, scaling to [0, 1]
        tiles_tensor = tiles_tensor.permute(0, 3, 1, 2).float() / 255.0  # (135, 3, 16, 16)
        # Upscale all tiles in one go using nearest-neighbor interpolation
        upscaled_tiles = F.interpolate(tiles_tensor, size=(640, 640), mode='nearest')
        preprocess_end = time.time()
        logger.debug(f"Tiles preprocessed (batch upscale) in {preprocess_end - preprocess_start:.2f} seconds")

        # Step 4: Run batch inference on all upscaled tiles
        inference_start = time.time()
        with torch.no_grad():
            outputs = self.model(upscaled_tiles.to(self.device))
            probs = torch.nn.functional.softmax(outputs, dim=1)
            top3 = torch.topk(probs, 3, dim=1)
        inference_end = time.time()
        logger.debug(f"Batch inference completed in {inference_end - inference_start:.2f} seconds")

        # Step 5: Assemble predictions per tile
        predictions = []
        for idx, (row, col) in enumerate(tile_positions):
            indices = top3.indices[idx].tolist()
            confs = top3.values[idx].tolist()
            class_names = [self.class_labels[i] for i in indices]
            predictions.append((row, col, class_names, confs))

        overall_end = time.time()
        logger.debug(f"Total image processing time: {overall_end - overall_start:.2f} seconds")
        return predictions

    def _load_class_names(self):
        """Load class names from a text file."""
        class_labels_path = Path(__file__).parent / "class_labels_run2.txt"
        if not os.path.exists(class_labels_path):
            raise FileNotFoundError("class_labels.txt not found. Run generate_class_labels.py first.")
        with open(class_labels_path, "r") as f:
            return [line.strip() for line in f.readlines()]
