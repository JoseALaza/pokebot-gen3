"""Map Graph - Manages connections between maps"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple, Dict, List, Optional


@dataclass
class MapConnection:
    """Represents a connection between two maps"""
    from_map: str
    from_tile: Tuple[int, int]
    to_map: str
    to_tile: Tuple[int, int]
    direction: str

    def to_dict(self) -> dict:
        return {
            "from_map": self.from_map,
            "from_tile": list(self.from_tile),
            "to_map": self.to_map,
            "to_tile": list(self.to_tile),
            "direction": self.direction
        }

    @staticmethod
    def from_dict(data: dict) -> 'MapConnection':
        return MapConnection(
            from_map=data["from_map"],
            from_tile=tuple(data["from_tile"]),
            to_map=data["to_map"],
            to_tile=tuple(data["to_tile"]),
            direction=data["direction"]
        )


class MapGraph:
    """
    Manages the graph of map connections.

    Stores which tiles connect to which other maps.
    Provides pathfinding and navigation queries.
    """

    def __init__(self, storage_path: Path):
        self.storage_path = storage_path / "map_connections.json"
        self.connections: Dict[str, List[MapConnection]] = {}
        self.load()

    def load(self):
        """Load connections from disk"""
        if not self.storage_path.exists():
            return

        try:
            with open(self.storage_path, 'r') as f:
                data = json.load(f)

            for map_key, conn_list in data.items():
                self.connections[map_key] = [
                    MapConnection.from_dict(c) for c in conn_list
                ]
        except Exception as e:
            print(f"Error loading map connections: {e}")

    def save(self):
        """Save connections to disk"""
        data = {}
        for map_key, conn_list in self.connections.items():
            data[map_key] = [c.to_dict() for c in conn_list]

        with open(self.storage_path, 'w') as f:
            json.dump(data, f, indent=2)

    def add_connection(
        self,
        from_map: str,
        from_tile: Tuple[int, int],
        to_map: str,
        to_tile: Tuple[int, int],
        direction: str
    ):
        """
        Add a bidirectional connection between two maps.

        Args:
            from_map: Source map key
            from_tile: Exit tile coordinates
            to_map: Destination map key
            to_tile: Entry tile coordinates
            direction: Direction of movement
        """
        # Forward connection
        forward = MapConnection(from_map, from_tile, to_map, to_tile, direction)

        if from_map not in self.connections:
            self.connections[from_map] = []

        if not any(c.from_tile == from_tile and c.to_map == to_map
                   for c in self.connections[from_map]):
            self.connections[from_map].append(forward)

        # Reverse connection
        reverse_dir = {
            "Up": "Down", "Down": "Up",
            "Left": "Right", "Right": "Left"
        }.get(direction, direction)

        reverse = MapConnection(to_map, to_tile, from_map, from_tile, reverse_dir)

        if to_map not in self.connections:
            self.connections[to_map] = []

        if not any(c.from_tile == to_tile and c.to_map == from_map
                   for c in self.connections[to_map]):
            self.connections[to_map].append(reverse)

        self.save()

    def get_connections(self, map_key: str) -> List[MapConnection]:
        """Get all connections from a map"""
        return self.connections.get(map_key, [])

    def find_path(self, from_map: str, to_map: str) -> Optional[List[str]]:
        """
        Find shortest path between two maps using BFS.

        Returns:
            List of map keys representing the path, or None if no path exists
        """
        if from_map == to_map:
            return [from_map]

        visited = set()
        queue = [(from_map, [from_map])]

        while queue:
            current, path = queue.pop(0)

            if current in visited:
                continue

            visited.add(current)

            for conn in self.get_connections(current):
                if conn.to_map == to_map:
                    return path + [to_map]

                if conn.to_map not in visited:
                    queue.append((conn.to_map, path + [conn.to_map]))

        return None
