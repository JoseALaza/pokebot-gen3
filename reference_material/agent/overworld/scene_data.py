# scene_data.py

from .global_map import GlobalMap

class SceneData:
    """
    Holds two parallel GlobalMaps for a single scene:
      1) tile_map: store ResNet labels (e.g. "grass", "npc_up", "door")
      2) trav_map: store 'Y', 'N', 'S', etc. for passable / blocked / portal
    """

    def __init__(self):
        self.tile_map = GlobalMap(default_value="?")
        self.trav_map = GlobalMap(default_value="?")

    def __str__(self):
        tile_str = "=== TILE MAP ===\n" + str(self.tile_map)
        trav_str = "=== TRAV MAP ===\n" + str(self.trav_map)
        return f"{tile_str}\n\n{trav_str}"
