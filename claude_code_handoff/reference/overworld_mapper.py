# overworld_mapper.py

import logging
from pathlib import Path

from .scene_data import SceneData
from src.agent.overworld.map_enums import MapFRLG

logger = logging.getLogger(__name__)

def _normalize_map_tuple(map_tuple):
    """
    If (group, number) is recognized in MapFRLG, return that enum member.
    Otherwise, return the raw (group, number).
    """
    try:
        return MapFRLG(map_tuple)
    except ValueError:
        return map_tuple

# The center of the 9x15 local grid
AGENT_CENTER = (4, 7)

class OverworldMapper:
    """
    Memory-based scene detection + merges local ResNet tile data into
    per-map SceneData. Now highlights current player position with "P".

    Also includes `get_player_pos()` returning (map_id, x, y, facing_dir).
    """

    def __init__(self, emulator, vision_tool):
        self.emulator = emulator
        self.vision_tool = vision_tool

        # Dictionary: key = MapFRLG or (group, number), val = SceneData
        self.scenes = {}

        # Last local grid for direction checks
        self.last_local_grid = None

        # Read initial map + coords
        initial_map_tuple = self.emulator.get_map_id()  # e.g. (3,0)
        self.prev_map_id = _normalize_map_tuple(initial_map_tuple)
        self.prev_x, self.prev_y = self.emulator.get_player_xy()

        # Ensure we have SceneData
        if self.prev_map_id not in self.scenes:
            self.scenes[self.prev_map_id] = SceneData()

    def update(self):
        """
        1) Check if map changed => new scene
        2) If same scene, check movement
        3) Capture local 9x15 tile grid
        4) Merge tiles into scene data, resetting any "P" => "Y" first,
           then marking new player position => "P"
        5) Save local grid in self.last_local_grid (so we can parse direction)
        """
        curr_map_tuple = self.emulator.get_map_id()
        curr_map_id = _normalize_map_tuple(curr_map_tuple)
        curr_x, curr_y = self.emulator.get_player_xy()

        old_map_id = self.prev_map_id
        old_x = self.prev_x
        old_y = self.prev_y

        msg = ""
        if curr_map_id != old_map_id:
            msg += f"Scene changed from {self._map_id_str(old_map_id)} to {self._map_id_str(curr_map_id)}\n"
            if curr_map_id not in self.scenes:
                msg += "Creating new scene\n"
                self.scenes[curr_map_id] = SceneData()
        else:
            # same scene => check movement
            if (curr_x, curr_y) == (old_x, old_y):
                msg += "No movement (blocked or no input)\n"
            else:
                msg += f"Moved from ({old_x},{old_y}) to ({curr_x},{curr_y}) in {self._map_id_str(curr_map_id)}\n"

        # Capture local 9x15
        local_grid = self._capture_local_grid()
        local_grid[AGENT_CENTER[0]][AGENT_CENTER[1]] = f"player{local_grid[AGENT_CENTER[0]][AGENT_CENTER[1]][3:]}"
        self.last_local_grid = local_grid  # store for facing checks

        # Merge
        scene_data = self.scenes[curr_map_id]
        self._merge_local_grid(scene_data, curr_x, curr_y, local_grid)

        # Update
        self.prev_map_id = curr_map_id
        self.prev_x = curr_x
        self.prev_y = curr_y



        return msg

    def _capture_local_grid(self):
        """
        Takes a screenshot, runs ResNet, returns a 9x15 array of labels.
        """
        screenshot_path = self.emulator.get_screenshot()
        predictions = self.vision_tool.process_image(screenshot_path)

        rows, cols = 9, 15
        local_grid = [["" for _ in range(cols)] for _ in range(rows)]
        for (r, c, labels, confs) in predictions:
            local_grid[r][c] = labels[0]
        return local_grid

    def _merge_local_grid(self, scene_data, player_x, player_y, local_grid):
        """
        - tile_map: always overwrite with newest label
        - trav_map: 
            * Reset any 'P' => 'Y'
            * If trav_map was '?' and label is 'tree'/'black', set 'N'
            * Finally set the player's current tile => 'P'
        """
        # 1) Convert all existing 'P' => 'Y' (just in this scene's trav_map)
        self._reset_player_marker(scene_data)

        # 2) Overwrite tile_map and partially update trav_map
        rows = len(local_grid)
        cols = len(local_grid[0]) if rows > 0 else 0

        for r in range(rows):
            for c in range(cols):
                global_x = player_x + (c - AGENT_CENTER[1])
                global_y = player_y + (r - AGENT_CENTER[0])

                # Check if global coordinates are within allowed range
                if global_x >= 0 and global_y >= 0:
                    label = local_grid[r][c]
                    # tile_map => always overwrite
                    scene_data.tile_map.set(global_y, global_x, label)

                    # trav_map => set 'N' if it's '?' and label is 'tree'/'black'
                    current_val = scene_data.trav_map.get(global_y, global_x)
                    if current_val == "?":
                        if label in {"tree", "black"}:
                            scene_data.trav_map.set(global_y, global_x, "N")
                        else:
                            scene_data.trav_map.set(global_y, global_x, "?")

        # 3) Mark player's current tile => 'P'
        scene_data.trav_map.set(player_y, player_x, "P")

    def _reset_player_marker(self, scene_data):
        """
        Revert any 'P' to 'Y' in trav_map. Called before marking new position.
        """
        gmap = scene_data.trav_map
        # We can brute force by iterating gmap.grid:
        for row_index in range(len(gmap.grid)):
            for col_index in range(len(gmap.grid[0])):
                if gmap.grid[row_index][col_index] == "P":
                    gmap.grid[row_index][col_index] = "Y"

    def print_scene(self, map_id=None):
        """
        Debug printing. If no map_id given, uses current.
        """
        if map_id is None:
            map_id = self.prev_map_id
        if map_id not in self.scenes:
            print(f"No data for map_id={map_id}")
            return

        print(f"Scene: {self._map_id_str(map_id)}")
        print(self.scenes[map_id])

    def convert_tile_map(self, map_id=None):
        """
        Converts the tile_map of a given scene to a array of array or csv.
        """
        if map_id is None:
            map_id = self.prev_map_id
        if map_id not in self.scenes:
            print(f"No data for map_id={map_id}")
            return
        
        tile_map_str = str(self.scenes[map_id].tile_map)
        logger.debug(f"Tile Map for {self._map_id_str(map_id)}:\n{tile_map_str}\n{type(tile_map_str)}")

        rows = tile_map_str.strip().split('\n')
        tile_m = [row.split() for row in rows]

        csv_data = "x,y,tile\n"  # Header row
        for y, row in enumerate(tile_m):
            for x, tile in enumerate(row):
                csv_data += f"{x},{y},{tile}\n"

        return csv_data
    
    def convert_trav_map(self, map_id=None):
        """
        Converts the traversal_map of a given scene to a array of array or csv.
        """
        if map_id is None:
            map_id = self.prev_map_id
        if map_id not in self.scenes:
            print(f"No data for map_id={map_id}")
            return
        
        trav_map_str = str(self.scenes[map_id].trav_map)
        logger.debug(f"Tile Map for {self._map_id_str(map_id)}:\n{trav_map_str}\n{type(trav_map_str)}")

        rows = trav_map_str.strip().split('\n')
        tile_m = [row.split() for row in rows]

        csv_data = "x,y,tile\n"  # Header row
        for y, row in enumerate(tile_m):
            for x, tile in enumerate(row):
                csv_data += f"{x},{y},{tile}\n"

        return csv_data

    def get_player_pos(self):
        """
        Returns (map_id, x, y, facing_dir).
        facing_dir derived by checking the center tile in self.last_local_grid.
        If unknown, returns "Up" by default or "None".
        """
        map_id = self.prev_map_id
        x, y = self.prev_x, self.prev_y

        # If we want to glean direction from the center tile
        facing_dir = None
        if self.last_local_grid:
            center_label = self.last_local_grid[AGENT_CENTER[0]][AGENT_CENTER[1]].lower()
            # e.g. "npc_left", "npc_right", ...
            # or "player_left"? depends how your labels are named
            for sub, dirval in {
                "player_up": "Up",
                "player_down": "Down",
                "player_left": "Left",
                "player_right": "Right",
            }.items():
                if sub in center_label:
                    facing_dir = dirval
                    break
            # fallback if not found
            if facing_dir is None:
                facing_dir = "Unknown"
        else:
            facing_dir = "Unknown"

        return (map_id, x, y, facing_dir)

    def _map_id_str(self, map_id):
        if isinstance(map_id, MapFRLG):
            return f"{map_id.pretty_name} (group={map_id.group}, number={map_id.number})"
        else:
            g, n = map_id
            return f"(group={g}, number={n})"

    def save_all_maps(self, out_dir="src/agent/agent_memory/overworld"):
        p = Path(out_dir)
        p.mkdir(parents=True, exist_ok=True)

        for map_id, scene_data in self.scenes.items():
            # Create a filename
            if isinstance(map_id, MapFRLG):
                file_stem = f"{map_id.name}_{map_id.group}_{map_id.number}"
            else:
                g, n = map_id
                file_stem = f"Map_{g}_{n}"

            tile_file = p / f"{file_stem}_tile_map.txt"
            trav_file = p / f"{file_stem}_trav_map.txt"

            with open(tile_file, "w", encoding="utf-8") as f:
                f.write(str(scene_data.tile_map))
            with open(trav_file, "w", encoding="utf-8") as f:
                f.write(str(scene_data.trav_map))
