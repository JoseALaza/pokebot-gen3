# global_map.py
import logging
logger = logging.getLogger(__name__)

class GlobalMap:
    """
    A 2D grid that expands as needed to store arbitrary values.
    You can store strings like "?", "Y", "N", or actual tile labels.
    """

    def __init__(self, default_value="?"):
        self.grid = [[default_value]]
        self.row_offset = 0
        self.col_offset = 0
        self.default_value = default_value

    def get(self, r, c):
        """
        Returns the map value at (r, c).
        If out of bounds, return default_value.
        """
        local_r = r - self.row_offset
        local_c = c - self.col_offset
        if 0 <= local_r < len(self.grid) and 0 <= local_c < len(self.grid[0]):
            return self.grid[local_r][local_c]
        return self.default_value

    def set(self, r, c, value):
        """
        Expands the 2D array if needed, then sets the cell to the given value.
        """
        local_r = r - self.row_offset
        local_c = c - self.col_offset

        # Expand upward
        while local_r < 0:
            self.grid.insert(0, [self.default_value] * len(self.grid[0]))
            self.row_offset -= 1
            local_r += 1

        # Expand downward
        while local_r >= len(self.grid):
            self.grid.append([self.default_value] * len(self.grid[0]))

        # Expand left
        while local_c < 0:
            for row in self.grid:
                row.insert(0, self.default_value)
            self.col_offset -= 1
            local_c += 1

        # Expand right
        while local_c >= len(self.grid[0]):
            for row in self.grid:
                row.append(self.default_value)

        # Finally set the value
        self.grid[local_r][local_c] = value

    def __str__(self):
        return "\n".join(" ".join(str(cell) for cell in row) for row in self.grid)
