"""
Map Visualizer - Converts JSON maps to visual representation

Usage:
    python visualize_map.py <path_to_map.json>
    python visualize_map.py <path_to_map.json> --compact
    python visualize_map.py <path_to_map.json> --full
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any


# Tile name abbreviations for compact view
TILE_ABBREV = {
    # Terrain
    "tree": "TRE",
    "path": "PTH",
    "tall_grass": "GRS",
    "rock": "ROK",
    "water": "WAT",
    "black": "BLK",
    "white": "WHT",
    "unknown": "???",
    
    # Buildings
    "building": "BLD",
    "poke_center": "PKC",
    "poke_mart": "PKM",
    "gym": "GYM",
    "door": "DOR",
    "outside_door": "ODR",
    "window": "WIN",
    "wall": "WAL",
    "floor_tile": "FLR",
    
    # Objects
    "mailbox": "MBX",
    "sign": "SGN",
    "flower_pot": "FLW",
    "flower_bed": "FLB",
    "fence": "FNC",
    "ladder_up": "LUP",
    "ladder_down": "LDN",
    "stairs": "STR",
    
    # NPCs
    "npc_up": "NPU",
    "npc_down": "NPD",
    "npc_left": "NPL",
    "npc_right": "NPR",
    "npc_pose": "NPC",

    "player":"PLA",
    
    # Interactive
    "teleport_tile": "TEL",
    "healing_station": "HEL",
    "pc_terminal": "PC ",
    
    # Water types
    "calm_water": "WTR",
    "surf_water": "SRF",
    "waterfall": "WTF",
    "rock_water": "RWR",
    
    # Cave
    "cave_path": "CVP",
    "cave_exit": "CVE",
    "rock_wall": "RWL",
    
    # Indoor
    "counter": "CNT",
    "table": "TBL",
    "chair": "CHR",
    "bed": "BED",
    "sofa": "SOF",
    "desk": "DSK",
    "shelf": "SHF",
    "cabinet": "CAB",
    "bookshelf": "BKS",
    
    # Items
    "pokeball": "PKB",
    "pokedex": "PDX",
    "machine": "MCH",
    
    # Misc
    "partition": "PRT",
    "pillar": "PLR",
    "statue": "STA",
    "painting": "PNT",
    "vending_machine": "VND",
}


def abbreviate_tile(tile_name: str) -> str:
    """Convert tile name to 3-character abbreviation"""
    return TILE_ABBREV.get(tile_name, tile_name[:3].upper())


def visualize_map_compact(json_path: Path):
    """Visualize map with compact 3-letter abbreviations"""
    with open(json_path, 'r') as f:
        map_data = json.load(f)
    
    print("=" * 100)
    print(f"MAP: {map_data['map_name']}")
    print(f"Key: {map_data['map_key']} | Group: {map_data['map_group']} | Number: {map_data['map_number']}")
    print(f"Bounds: {map_data['bounds']}")
    print(f"Visits: {map_data['visit_count']} | Created: {map_data['created_at'][:10]}")
    print("=" * 100)
    print()
    
    tile_map = map_data['tile_map']
    traversal_map = map_data['traversal_map']
    
    if not tile_map or not traversal_map:
        print("Map is empty!")
        return
    
    # Get dimensions
    height = len(tile_map)
    width = max(len(row) for row in tile_map) if height > 0 else 0
    
    print("=" * 100)
    print("TILE MAP (Compact - 3 Letter Codes)")
    print("=" * 100)
    
    # Header with column numbers
    print("     ", end="")
    for x in range(width):
        print(f"{x:3d} ", end="")
    print()
    print("    " + "----" * width)
    
    # Print rows with abbreviations
    for y, row in enumerate(tile_map):
        print(f"{y:3d} |", end="")
        for tile in row:
            abbrev = abbreviate_tile(tile)
            print(f" {abbrev}", end="")
        print()
    
    print()
    print("=" * 100)
    print("TRAVERSAL MAP")
    print("=" * 100)
    print("Legend: ? = Unknown | W = Walkable | N = Blocked | P = Player | T = Traversal | I = Interactable")
    print("=" * 100)
    
    # Header
    print("     ", end="")
    for x in range(width):
        print(f" {x:2d}", end="")
    print()
    print("    " + "---" * width)
    
    # Print traversal map with color coding
    for y, row in enumerate(traversal_map):
        print(f"{y:3d} |", end="")
        for marker in row:
            # Color code the markers
            if marker == 'W':
                print(f" \033[92m{marker}\033[0m ", end="")  # Green
            elif marker == 'N':
                print(f" \033[91m{marker}\033[0m ", end="")  # Red
            elif marker == 'P':
                print(f" \033[94m{marker}\033[0m ", end="")  # Blue
            elif marker == 'T':
                print(f" \033[93m{marker}\033[0m ", end="")  # Yellow
            elif marker == 'I':
                print(f" \033[95m{marker}\033[0m ", end="")  # Magenta
            else:
                print(f" {marker} ", end="")  # White/default
        print()
    
    print()
    print_statistics(tile_map, traversal_map)


def visualize_map_full(json_path: Path):
    """Visualize map with full tile names (original format but better aligned)"""
    with open(json_path, 'r') as f:
        map_data = json.load(f)
    
    print("=" * 120)
    print(f"MAP: {map_data['map_name']}")
    print(f"Key: {map_data['map_key']} | Bounds: {map_data['bounds']} | Visits: {map_data['visit_count']}")
    print("=" * 120)
    print()
    
    tile_map = map_data['tile_map']
    traversal_map = map_data['traversal_map']
    
    if not tile_map or not traversal_map:
        print("Map is empty!")
        return
    
    print("TILE MAP (Full Names)")
    print("=" * 120)
    
    # Find the longest tile name for alignment
    max_tile_len = max(len(tile) for row in tile_map for tile in row)
    max_tile_len = min(max_tile_len, 15)  # Cap at 15 characters
    
    # Print with better formatting
    for y, row in enumerate(tile_map):
        print(f"{y:3d}: ", end="")
        for tile in row:
            # Truncate if needed and pad
            tile_display = tile[:max_tile_len].ljust(max_tile_len)
            print(f"{tile_display} ", end="")
        print()
    
    print()
    print("TRAVERSAL MAP")
    print("=" * 120)
    
    for y, row in enumerate(traversal_map):
        print(f"{y:3d}: ", end="")
        for marker in row:
            print(f"{marker:2s} ", end="")
        print()
    
    print()
    print_statistics(tile_map, traversal_map)


def visualize_map_grid(json_path: Path):
    """Visualize map with grid overlay (best for analysis)"""
    with open(json_path, 'r') as f:
        map_data = json.load(f)
    
    print("\n" + "=" * 100)
    print(f"MAP: {map_data['map_name']} ({map_data['map_key']})")
    print(f"Bounds: ({map_data['bounds']['min_x']}, {map_data['bounds']['min_y']}) to "
          f"({map_data['bounds']['max_x']}, {map_data['bounds']['max_y']})")
    print("=" * 100 + "\n")
    
    tile_map = map_data['tile_map']
    traversal_map = map_data['traversal_map']
    
    if not tile_map or not traversal_map:
        print("Map is empty!")
        return
    
    height = len(tile_map)
    width = max(len(row) for row in tile_map) if height > 0 else 0
    
    print("COMBINED VIEW (Tile/Traversal)")
    print("Format: [Tile Abbrev][Trav]")
    print("=" * 100)
    
    # Header
    print("      ", end="")
    for x in range(width):
        print(f"  {x:2d}  ", end="")
    print()
    print("     +" + "-----+" * width)
    
    # Combined view
    for y in range(height):
        print(f"{y:3d}  |", end="")
        for x in range(width):
            if x < len(tile_map[y]) and x < len(traversal_map[y]):
                tile = tile_map[y][x]
                trav = traversal_map[y][x]
                tile_abbrev = abbreviate_tile(tile)
                
                # Color code based on traversal
                if trav == 'W':
                    print(f"\033[92m{tile_abbrev}{trav}\033[0m|", end="")  # Green
                elif trav == 'N':
                    print(f"\033[91m{tile_abbrev}{trav}\033[0m|", end="")  # Red
                elif trav == 'P':
                    print(f"\033[94m{tile_abbrev}{trav}\033[0m|", end="")  # Blue
                elif trav == 'T':
                    print(f"\033[93m{tile_abbrev}{trav}\033[0m|", end="")  # Yellow
                else:
                    print(f"{tile_abbrev}{trav}|", end="")
            else:
                print("    |", end="")
        print()
        print("     +" + "-----+" * width)
    
    print()
    print_statistics(tile_map, traversal_map)


def print_statistics(tile_map, traversal_map):
    """Print tile and traversal statistics"""
    # Tile statistics
    tile_counts = {}
    for row in tile_map:
        for tile in row:
            tile_counts[tile] = tile_counts.get(tile, 0) + 1
    
    # Traversal statistics
    trav_counts = {}
    for row in traversal_map:
        for marker in row:
            trav_counts[marker] = trav_counts.get(marker, 0) + 1
    
    print("=" * 100)
    print("STATISTICS")
    print("=" * 100)
    
    # Split into columns
    print("\nTOP 10 TILES:".ljust(50) + "TRAVERSAL STATUS:")
    print("-" * 50 + "-" * 50)
    
    # Get top 10 tiles
    top_tiles = sorted(tile_counts.items(), key=lambda x: -x[1])[:10]
    
    # Traversal items
    trav_items = [
        ('?', 'Unknown', trav_counts.get('?', 0)),
        ('W', 'Walkable', trav_counts.get('W', 0)),
        ('N', 'Blocked', trav_counts.get('N', 0)),
        ('P', 'Player', trav_counts.get('P', 0)),
        ('T', 'Traversal', trav_counts.get('T', 0)),
        ('I', 'Interactable', trav_counts.get('I', 0)),
    ]
    
    # Print side by side
    for i in range(max(len(top_tiles), len(trav_items))):
        # Left column (tiles)
        if i < len(top_tiles):
            tile, count = top_tiles[i]
            tile_str = f"{i+1:2d}. {tile:20s}: {count:4d}"
        else:
            tile_str = " " * 50
        
        # Right column (traversal)
        if i < len(trav_items):
            marker, name, count = trav_items[i]
            trav_str = f"{marker} ({name:12s}): {count:4d}"
        else:
            trav_str = ""
        
        print(tile_str + trav_str)
    
    print("\n" + "=" * 100)
    
    # Summary
    total_tiles = sum(tile_counts.values())
    explored_tiles = sum(count for marker, count in trav_counts.items() if marker != '?')
    
    print(f"\nTotal Tiles: {total_tiles}")
    print(f"Explored: {explored_tiles} ({explored_tiles/total_tiles*100:.1f}%)")
    print(f"Unique Tile Types: {len(tile_counts)}")


def print_legend():
    """Print legend of tile abbreviations"""
    print("\n" + "=" * 100)
    print("TILE ABBREVIATION LEGEND")
    print("=" * 100)
    
    # Group abbreviations by category
    categories = {
        "Terrain": ["tree", "path", "tall_grass", "rock", "water", "black", "white"],
        "Buildings": ["building", "poke_center", "poke_mart", "gym", "door", "outside_door", "window", "wall", "floor_tile"],
        "Objects": ["mailbox", "sign", "flower_pot", "fence", "ladder_up", "ladder_down", "stairs"],
        "NPCs": ["npc_up", "npc_down", "npc_left", "npc_right", "npc_pose"],
        "Interactive": ["teleport_tile", "healing_station", "pc_terminal"],
    }
    
    for category, tiles in categories.items():
        print(f"\n{category}:")
        for tile in tiles:
            if tile in TILE_ABBREV:
                print(f"  {TILE_ABBREV[tile]} = {tile}")
    
    print("\n" + "=" * 100)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python visualize_map.py <path_to_map.json> [--compact|--full|--grid|--legend]")
        print("\nOptions:")
        print("  --compact (default): 3-letter tile codes, easy to read")
        print("  --full: Full tile names (may wrap)")
        print("  --grid: Combined tile+traversal view with grid")
        print("  --legend: Show tile abbreviation legend")
        sys.exit(1)
    
    json_path = Path(sys.argv[1])
    if not json_path.exists():
        print(f"File not found: {json_path}")
        sys.exit(1)
    
    # Determine mode
    mode = "compact"  # Default
    if len(sys.argv) > 2:
        if sys.argv[2] == "--full":
            mode = "full"
        elif sys.argv[2] == "--grid":
            mode = "grid"
        elif sys.argv[2] == "--legend":
            print_legend()
            sys.exit(0)
    
    # Visualize
    if mode == "compact":
        visualize_map_compact(json_path)
    elif mode == "full":
        visualize_map_full(json_path)
    elif mode == "grid":
        visualize_map_grid(json_path)
