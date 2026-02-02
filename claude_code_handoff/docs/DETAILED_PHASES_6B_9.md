# Detailed Implementation Guide - Phases 6B through 9

This document provides step-by-step instructions for implementing each remaining phase.

---

## Phase 6B: Enhanced Outcome Detection

**Goal**: Robust movement outcome tracking with edge case handling

### Current Implementation (llm_trainer.py lines 130-180)

The current `_check_action_outcome()` method handles basic cases:
- Movement (position changed)
- Turn (facing changed, position same)
- Blocked (neither changed)
- Map change (map_name different)

### Problems to Fix:

#### Problem 1: Repeated Blocked Marking

**Current behavior**:
```
Decision # 17: Up - blocked at (4,7)
Decision # 18: Up - blocked at (4,7)  ← Same tile marked again!
Decision # 19: Up - blocked at (4,7)  ← And again!
```

**Solution**: Track last blocked tile, don't re-mark if same

```python
# Add to LLMTrainerMode.__init__
self.last_blocked_tile: Optional[Tuple[int, int]] = None

# In outcome detection (Phase 6B)
elif outcome["type"] == "blocked":
    target_x, target_y = self.map_manager.calculate_target_tile(...)
    
    # Only mark if different from last blocked tile
    if (target_x, target_y) != self.last_blocked_tile:
        self.map_manager.set_traversal_at(target_x, target_y, 'N')
        console.print(f"[red]  → Marked tile ({target_x}, {target_y}) as BLOCKED[/]")
        self.last_blocked_tile = (target_x, target_y)
    else:
        console.print(f"[dim red]  → Tile ({target_x}, {target_y}) already marked as blocked[/]")

# Reset on successful movement
elif outcome["type"] == "movement":
    self.last_blocked_tile = None
    # ... rest of movement handling
```

#### Problem 2: Incorrect Blocked Detection During Turns

**Current issue**: When player turns while blocked, we may mark wrong tile

**Example**:
```
Player at (4,8) facing Up
Action: Right (turn + move)
Result: Player turned Right but didn't move (wall on right)
Bug: We mark tile to the Right as blocked, but player is still facing Up!
```

**Solution**: Check if position changed AFTER waiting for movement to complete

```python
# In run() method, after executing action
# Current: Wait 5 frames
for _ in range(5):
    yield
    self.frame_count += 1

# Problem: 5 frames may not be enough for all movements
# Solution: Wait until position stabilizes

# Better approach:
frames_to_wait = 10  # Increased from 5
position_stable_count = 0
last_check_pos = old_pos

for frame in range(frames_to_wait):
    yield
    self.frame_count += 1
    
    # Check if position has stabilized
    if frame >= 3:  # Start checking after 3 frames
        current_pos = (
            self.memory_reader.get_player_avatar().local_coordinates
        )
        if current_pos == last_check_pos:
            position_stable_count += 1
            if position_stable_count >= 2:
                break  # Position stable, movement complete
        else:
            position_stable_count = 0
            last_check_pos = current_pos
```

#### Problem 3: No Player State Detection

**Missing**: Can't detect when player is in menu, battle, or dialogue

**Solution**: Add game state checking

```python
# Add to MemoryReader class
def get_game_state_type(self) -> str:
    """
    Get current game state type.
    
    Returns:
        One of: "overworld", "battle", "menu", "dialogue", "unknown"
    """
    from modules.game import get_game_state
    from modules.state_cache import state_cache
    
    game_state = get_game_state()
    
    # Map pokebot states to our states
    if game_state.name == "OVERWORLD":
        return "overworld"
    elif game_state.name == "BATTLE":
        return "battle"
    elif game_state.name == "BAG_MENU" or game_state.name == "PARTY_MENU":
        return "menu"
    else:
        # Check if dialogue box is showing
        # This requires reading specific memory addresses
        # For now, return unknown
        return "unknown"

# In llm_trainer.py, before making decision
game_state_type = self.memory_reader.get_game_state_type()

if game_state_type == "battle":
    console.print("[red]In battle! Pausing LLM decisions.[/]")
    # Skip this decision cycle, just wait
    self.last_decision_frame = self.frame_count + self.decision_interval
    yield
    continue
elif game_state_type == "menu":
    console.print("[yellow]In menu. Pressing B to exit.[/]")
    context.emulator.press_button("B")
    # Wait for menu to close
    for _ in range(10):
        yield
    self.last_decision_frame = self.frame_count
    continue
```

#### Problem 4: Ledge Jumps

**Issue**: Ledge jumps are one-way movement (can jump down, can't return)

**Solution**: Mark ledge tiles specially

```python
# In MapManager, add new traversal marker
LEDGE = 'L'  # One-way ledge

# When detecting ledge jump (player moved 2+ tiles in one action)
if outcome["type"] == "movement":
    distance = abs(new_pos[0] - old_pos[0]) + abs(new_pos[1] - old_pos[1])
    
    if distance > 1:
        # Likely a ledge jump or warp
        console.print(f"[magenta]Detected multi-tile movement! Distance: {distance}[/]")
        
        # Mark old tile as ledge
        self.map_manager.set_traversal_at(old_pos[0], old_pos[1], 'L')
        
        # Mark new tile as walkable
        self.map_manager.set_traversal_at(new_pos[0], new_pos[1], 'W')
```

#### Problem 5: Warps (Doors/Caves)

**Issue**: Map changes should mark both tiles as traversal

**Current**: Only marks old position as T
**Better**: Mark both old (exit) and new (entry) positions, link them

```python
elif outcome["type"] == "map_change":
    # Mark old position as traversal in old map
    # (Old map is still loaded in map_manager.current_map_data)
    self.map_manager.set_traversal_at(old_pos[0], old_pos[1], 'T')
    
    # Calculate entry tile in new map
    # Player appeared at new_pos facing new_facing
    # They must have come from the opposite direction
    entry_x, entry_y = new_pos
    
    # Calculate where they came from
    reverse_direction = {
        "Up": "Down",
        "Down": "Up",
        "Left": "Right",
        "Right": "Left"
    }.get(new_facing, None)
    
    if reverse_direction:
        # Calculate the tile they came from
        from_x, from_y = self.map_manager.calculate_target_tile(
            entry_x, entry_y, reverse_direction
        )
        
        # This will be implemented in Phase 6C
        # For now, just mark entry tile
        console.print(
            f"[magenta]Map transition: "
            f"{old_map} ({old_pos[0]},{old_pos[1]}) → "
            f"{new_map} ({entry_x},{entry_y})[/]"
        )
```

### Testing Phase 6B

Create test scenarios:

1. **Test Repeated Blocking**:
   - Run bot until it hits a wall
   - Verify tile only marked once
   - Check last_blocked_tile is set

2. **Test Turn Detection**:
   - Manually create scenario where bot turns without moving
   - Verify correct tile marked as blocked

3. **Test State Detection**:
   - Open menu manually → verify bot presses B
   - Enter battle → verify bot pauses

4. **Test Ledge Jump**:
   - Position bot on ledge
   - Let it jump
   - Verify old tile marked as 'L'

5. **Test Warp**:
   - Let bot walk through door
   - Verify console shows entry tile calculation
   - Check both maps updated

---

## Phase 6C: Map Connectivity Graph

**Goal**: Build and store connections between maps

### Data Structures

#### MapConnection Class

```python
# File: modules/llm_trainer/map_graph.py

from dataclasses import dataclass
from typing import Tuple, Dict, List, Optional
import json
from pathlib import Path


@dataclass
class MapConnection:
    """Represents a connection between two maps"""
    from_map: str        # "map_3_0"
    from_tile: Tuple[int, int]  # (6, 7)
    to_map: str          # "map_4_0"
    to_tile: Tuple[int, int]    # (4, 8)
    direction: str       # "Up", "Down", etc.
    
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
        
        # Check if connection already exists
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
        
        return None  # No path found
```

### Integration with Map Manager

Add to `MapManager` class:

```python
# In MapManager.__init__
from modules.llm_trainer.map_graph import MapGraph

self.map_graph = MapGraph(self.maps_dir)

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
    # Exit tile is where player was
    exit_tile = old_position
    
    # Entry tile calculation:
    # Player appears at new_position facing new_facing
    # They came from the opposite direction
    reverse_dir = {
        "Up": "Down",
        "Down": "Up",
        "Left": "Right",
        "Right": "Left"
    }.get(new_facing, new_facing)
    
    # The tile they "came from" in the new map
    # is one tile back from where they appeared
    entry_tile_x, entry_tile_y = self.calculate_target_tile(
        new_position[0],
        new_position[1],
        reverse_dir
    )
    entry_tile = (entry_tile_x, entry_tile_y)
    
    # Add connection
    self.map_graph.add_connection(
        old_map_key,
        exit_tile,
        new_map_key,
        entry_tile,
        old_facing  # Direction used to exit
    )
    
    console.print(
        f"[magenta]Added connection: "
        f"{old_map_key} {exit_tile} → {new_map_key} {entry_tile}[/]"
    )
```

### Integration with Bot Mode

In `llm_trainer.py`, update map transition handling:

```python
# When map change detected
if self.map_manager.current_map_key != current_map_key:
    # Before saving/loading
    old_map_key = self.map_manager.current_map_key
    
    # Save old map
    if self.map_manager.current_map_data is not None:
        self.map_manager.save_map()
    
    # Load new map
    self.map_manager.load_map(...)
    
    # Record the transition (after both maps are loaded)
    if old_map_key is not None:  # Not first map
        self.map_manager.handle_map_transition(
            old_map_key,
            old_pos,
            old_facing,
            current_map_key,
            new_pos,
            new_facing
        )
```

### Testing Phase 6C

1. **Test Simple Transition**:
   - Exit house to Pallet Town
   - Check `map_connections.json` has bidirectional link
   - Verify entry/exit tiles are correct

2. **Test Multiple Transitions**:
   - Visit 3-4 connected maps
   - Check graph builds correctly
   - Verify pathfinding works

3. **Test Re-entry**:
   - Exit house, re-enter house
   - Check connection not duplicated
   - Verify existing connection reused

---

## Phase 7: Decision Logging

**Goal**: Save every decision with full context

### File Structure

```
profiles/<profile>/llm_trainer/sessions/
├── session_20260202_014437/
│   ├── metadata.json
│   ├── decision_001.json
│   ├── decision_002.json
│   └── ...
└── session_20260202_023015/
    └── ...
```

### Session Metadata

```json
{
  "session_id": "session_20260202_014437",
  "start_time": "2026-02-02T01:44:37",
  "end_time": null,
  "total_decisions": 93,
  "start_map": "map_3_0",
  "start_position": [6, 8],
  "agent_strategy": "explore",
  "llm_provider": "mock"
}
```

### Decision Log Entry

```json
{
  "decision_number": 15,
  "timestamp": "2026-02-02T01:45:12.345",
  "frame": 450,
  
  "game_state_before": {
    "player": {
      "position": {"x": 4, "y": 8},
      "facing": "Up",
      "map": "Pallet Town",
      "map_group": 3,
      "map_number": 0
    },
    "party": [...]
  },
  
  "vision_data": {
    "tile_map": [[...]],
    "screenshot_base64": "..."  // Optional
  },
  
  "decision": {
    "action": "Up",
    "reasoning": "Continuing Up to explore",
    "confidence": 0.7,
    "strategy": "explore"
  },
  
  "execution": {
    "success": true,
    "frames_waited": 5
  },
  
  "outcome": {
    "type": "blocked",
    "success": false,
    "reason": "Could not move Up - blocked by obstacle",
    "position_changed": false,
    "facing_changed": false,
    "new_position": {"x": 4, "y": 8},
    "new_facing": "Up",
    "new_map": "Pallet Town"
  }
}
```

### Implementation

```python
# File: modules/llm_trainer/decision_logger.py

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
import base64


class DecisionLogger:
    """Logs all decisions to JSON files for analysis"""
    
    def __init__(self, profile_path: Path):
        self.sessions_dir = profile_path / "llm_trainer" / "sessions"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        
        # Start new session
        self.session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.session_dir = self.sessions_dir / self.session_id
        self.session_dir.mkdir()
        
        self.metadata = {
            "session_id": self.session_id,
            "start_time": datetime.now().isoformat(),
            "end_time": None,
            "total_decisions": 0,
            "start_map": None,
            "start_position": None,
            "agent_strategy": None,
            "llm_provider": None
        }
        
        self._save_metadata()
    
    def _save_metadata(self):
        """Save session metadata"""
        with open(self.session_dir / "metadata.json", 'w') as f:
            json.dump(self.metadata, f, indent=2)
    
    def log_decision(
        self,
        decision_number: int,
        frame: int,
        game_state_before: Dict[str, Any],
        vision_data: Dict[str, Any],
        decision: Dict[str, Any],
        execution_success: bool,
        outcome: Dict[str, Any],
        include_screenshot: bool = False
    ):
        """Log a single decision"""
        
        entry = {
            "decision_number": decision_number,
            "timestamp": datetime.now().isoformat(),
            "frame": frame,
            "game_state_before": game_state_before,
            "vision_data": {
                "tile_map": vision_data.get("tile_map"),
                "tiles_x": vision_data.get("tiles_x"),
                "tiles_y": vision_data.get("tiles_y")
            },
            "decision": decision,
            "execution": {
                "success": execution_success
            },
            "outcome": outcome
        }
        
        # Optionally include screenshot
        if include_screenshot and "screenshot" in vision_data:
            # Convert numpy array to base64
            screenshot = vision_data["screenshot"]
            # ... encode to base64
            entry["vision_data"]["screenshot_base64"] = "..."
        
        # Save to file
        filename = f"decision_{decision_number:04d}.json"
        with open(self.session_dir / filename, 'w') as f:
            json.dump(entry, f, indent=2)
        
        # Update metadata
        self.metadata["total_decisions"] = decision_number
        self._save_metadata()
    
    def end_session(self):
        """Mark session as ended"""
        self.metadata["end_time"] = datetime.now().isoformat()
        self._save_metadata()
```

### Integration

Add to `llm_trainer.py`:

```python
# In __init__
from modules.llm_trainer.decision_logger import DecisionLogger

self.decision_logger = DecisionLogger(Path(context.profile.path))

# After outcome detection
self.decision_logger.log_decision(
    decision_number=self.agent.get_decision_count(),
    frame=self.frame_count,
    game_state_before=game_state_before,
    vision_data=vision_data,
    decision=decision,
    execution_success=success,
    outcome=outcome,
    include_screenshot=False  # Set True to save screenshots
)
```

---

## Phase 8 & 9: HTTP Server & Real LLM

Due to token limits, detailed implementation for these phases will be in separate files. Key points:

### Phase 8: HTTP Visualization

- Extend `modules/http/http_server.py`
- Add endpoints returning JSON
- Create frontend in `modules/http/static/llm/`
- Use existing pokebot HTTP infrastructure

### Phase 9: Real LLM Integration

- Create provider interfaces
- Each provider: `decide(state, vision) -> decision`
- Handle API keys via environment variables
- Implement token counting and cost tracking
- Error handling with exponential backoff

---

## Testing Strategy

For each phase:

1. **Unit Tests**: Test individual functions
2. **Integration Tests**: Test component interactions
3. **Live Tests**: Run bot and observe
4. **Edge Case Tests**: Deliberate edge cases
5. **Regression Tests**: Ensure old features still work

---

## Common Pitfalls

1. **Don't break Phase 6A**: Test frequently
2. **Memory leaks**: Clear old data periodically
3. **File I/O**: Always use try/except
4. **Thread safety**: pokebot is single-threaded, no locks needed
5. **Performance**: Profile if slow (vision is GPU-accelerated)

---

Ready to implement! Start with Phase 6B, test thoroughly, then move to 6C.
