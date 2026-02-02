# Codebase Reference Map

Quick reference for navigating the LLM Trainer codebase.

---

## File Structure

```
pokebot-gen3/
├── modules/
│   ├── modes/
│   │   └── llm_trainer.py              # Main bot mode orchestrator
│   └── llm_trainer/
│       ├── __init__.py
│       ├── memory_reader.py             # Game state extraction
│       ├── vision_processor.py          # ResNet tile classification
│       ├── action_executor.py           # Button press execution
│       ├── agent.py                     # Decision making (mock/real LLM)
│       ├── map_manager.py               # Map storage and management
│       ├── decision_logger.py           # TODO: Phase 7
│       ├── map_graph.py                 # TODO: Phase 6C
│       └── models/
│           ├── best_resnet.pth          # ResNet-18 trained weights
│           └── class_labels_run2.txt    # 103 tile class names
└── profiles/
    └── <profile_name>/
        └── llm_trainer/
            ├── maps/
            │   ├── map_3_0.json         # Pallet Town
            │   └── map_4_0.json         # Player's House (example)
            ├── sessions/                # TODO: Decision logs
            └── map_connections.json     # TODO: World graph
```

---

## Component Overview

### 1. Bot Mode (`modules/modes/llm_trainer.py`)

**Lines**: ~280  
**Purpose**: Main orchestrator that ties everything together

**Key Methods**:
- `__init__()` - Initialize all components
- `run()` - Main game loop (generator)
- `_check_action_outcome()` - Determine what happened after action

**Flow**:
```python
while True:
    if time_for_decision:
        read_game_state()
        process_vision()
        agent.decide()
        execute_action()
        wait_for_completion()
        detect_outcome()
        update_maps()
        log_results()
    yield  # One frame
```

**Dependencies**:
- MemoryReader
- VisionProcessor
- ActionExecutor
- Agent
- MapManager

---

### 2. Memory Reader (`modules/llm_trainer/memory_reader.py`)

**Lines**: ~200  
**Purpose**: Extract game state from emulator memory

**Key Methods**:
- `read_full_state()` → Complete state with party
- `read_lightweight_state()` → Fast state without party
- `has_player_moved()` → Detects position/map changes
- `has_map_changed()` → Detects map transitions
- `get_player_state()` → Position, facing, map
- `get_party_summary()` → Pokemon party info

**Data Structures**:
```python
{
  "player": {
    "position": {"x": 6, "y": 8},
    "facing": "Down",
    "map": "Pallet Town",
    "map_group": 3,
    "map_number": 0
  },
  "party": [
    {"species": "Charmander", "level": 5, ...},
    ...
  ],
  "frame": 12345
}
```

**pokebot APIs Used**:
- `get_player_avatar()` - Position and facing
- `get_map_data_for_current_position()` - Map info
- `get_party()` - Pokemon party

---

### 3. Vision Processor (`modules/llm_trainer/vision_processor.py`)

**Lines**: ~350  
**Purpose**: Convert screenshots to tile classifications

**Key Methods**:
- `process_frame()` → Full tile map + traversal map
- `get_screenshot()` → NumPy array from emulator
- `crop_screenshot()` → Remove top/bottom margins
- `extract_tiles()` → Split into 16x16 tiles
- `classify_tiles_resnet()` → Batch inference
- `classify_tiles_placeholder()` → Fallback if no model

**Processing Pipeline**:
```
PIL Image (240×160)
    ↓ get_screenshot()
NumPy (160, 240, 3)
    ↓ crop_screenshot()
NumPy (144, 240, 3)
    ↓ extract_tiles()
NumPy (135, 16, 16, 3)
    ↓ classify_tiles_resnet()
List[List[str]] (9×15 grid)
```

**ResNet Details**:
- Model: ResNet-18
- Input: 640×640 (upscaled from 16×16)
- Output: 103 classes
- Batch size: 135 tiles
- Device: CUDA if available, else CPU

**Tile Classes** (103 total):
- Terrain: `tree`, `path`, `tall_grass`, `rock`, `water`
- Buildings: `building`, `poke_center`, `poke_mart`
- Objects: `mailbox`, `sign`, `flower_pot`, `fence`
- Interactive: `outside_door`, `npc_left`, `npc_up`, `npc_down`, `npc_right`
- Indoor: `floor_tile`, `wall`, `stairs`, `window`
- Special: `teleport_tile`, `ladder_up`, `ladder_down`

---

### 4. Action Executor (`modules/llm_trainer/action_executor.py`)

**Lines**: ~120  
**Purpose**: Execute button presses in emulator

**Valid Actions**:
- Directional: `Up`, `Down`, `Left`, `Right`
- Buttons: `A`, `B`, `Start`, `Select`
- Special: `WAIT` (do nothing)

**Key Methods**:
- `execute(action)` → Execute button press
- `get_stats()` → Execution statistics

**Case Sensitivity**:
- pokebot requires exact case: `Up` not `UP`
- Action executor handles normalization

**Pokemon Movement**:
- First press: Turn to face direction
- Second press: Move in that direction
- Exception: If already facing, just move

---

### 5. Agent (`modules/llm_trainer/agent.py`)

**Lines**: ~180  
**Purpose**: Make decisions (mock LLM or real LLM)

**Mock Strategies**:
- `random` - Random walk
- `scripted_exit_house` - Hardcoded sequence to exit house
- `explore` - Basic exploration (prefer continuing direction)

**Key Methods**:
- `decide(game_state, vision_data)` → Decision dict
- `get_decision_count()` → Total decisions made
- `get_recent_decisions(n)` → Last N decisions

**Decision Format**:
```python
{
  "action": "Up",
  "reasoning": "Continuing Up to explore",
  "confidence": 0.7,
  "strategy": "explore",
  "step": 15,
  "timestamp": "2026-02-02T01:45:12",
  "frame": 450,
  "decision_number": 15
}
```

**Real LLM Integration** (Phase 9):
- Replace `MockLLM` with `RealLLM`
- Keep same interface
- Add token tracking

---

### 6. Map Manager (`modules/llm_trainer/map_manager.py`)

**Lines**: ~420  
**Purpose**: Store and manage maps for each area

**Key Methods**:

**Map Loading/Saving**:
- `load_map(name, group, number)` → Load or create map
- `save_map(map_data)` → Save to JSON
- `_get_map_key(group, number)` → Generate unique key

**Tile Access**:
- `get_tile_at(x, y)` → Get tile name at coords
- `get_traversal_at(x, y)` → Get traversal marker
- `set_traversal_at(x, y, marker)` → Set traversal marker

**Map Updates**:
- `update_tile_map_from_screen(player_x, player_y, screen_tiles)` → Update from vision
- `_ensure_map_size(max_x, max_y)` → Expand map as needed

**Utilities**:
- `calculate_target_tile(x, y, direction)` → Get tile in direction
- `get_map_summary()` → Summary string

**Data Structure**:
```python
{
  "map_key": "map_3_0",
  "map_name": "Pallet Town",
  "map_group": 3,
  "map_number": 0,
  "tile_map": [[str, ...], ...],      # 2D array of tile names
  "traversal_map": [[str, ...], ...],  # 2D array of markers
  "bounds": {"min_x": 0, "min_y": 0, "max_x": 13, "max_y": 16},
  "visit_count": 1,
  "created_at": "ISO timestamp",
  "last_updated": "ISO timestamp"
}
```

**Coordinate System**:
- Each map: Independent (0,0) origin
- Player: Game coordinates preserved
- Screen: 15×9 tiles, player at center (7, 4)

---

## Data Flow Diagram

```
┌─────────────────┐
│  Emulator RAM   │
└────────┬────────┘
         │ read memory
         ↓
┌─────────────────┐      ┌──────────────────┐
│ Memory Reader   │      │ Emulator Screen  │
└────────┬────────┘      └────────┬─────────┘
         │                        │ screenshot
         │                        ↓
         │               ┌──────────────────┐
         │               │ Vision Processor │
         │               └────────┬─────────┘
         │                        │ tile classifications
         ↓                        ↓
    ┌─────────────────────────────────┐
    │          Agent                  │
    │  (receives state + vision)      │
    └────────┬────────────────────────┘
             │ decision
             ↓
    ┌─────────────────┐
    │ Action Executor │
    └────────┬────────┘
             │ button press
             ↓
    ┌─────────────────┐
    │   Emulator      │ ◄──────┐
    └─────────────────┘        │
             │                 │
             │ outcome         │
             ↓                 │
    ┌─────────────────┐        │
    │  Outcome Check  │        │
    └────────┬────────┘        │
             │                 │
             ↓                 │
    ┌─────────────────┐        │
    │  Map Manager    │        │
    │  (update maps)  │        │
    └────────┬────────┘        │
             │                 │
             │ save            │
             ↓                 │
    ┌─────────────────┐        │
    │  JSON Files     │        │
    └─────────────────┘        │
                               │
    ┌─────────────────┐        │
    │ Decision Logger │ ───────┘
    │   (Phase 7)     │
    └─────────────────┘
```

---

## Key Algorithms

### Screen to World Coordinate Mapping

```python
def screen_to_world(player_x, player_y, screen_row, screen_col):
    """
    Convert screen-relative coordinates to world coordinates.
    
    Player is at center of 15×9 screen: position (7, 4)
    """
    screen_width = 15
    screen_height = 9
    player_screen_col = 7
    player_screen_row = 4
    
    # Calculate top-left corner of screen in world coords
    screen_top_left_x = player_x - player_screen_col
    screen_top_left_y = player_y - player_screen_row
    
    # Map screen tile to world tile
    world_x = screen_top_left_x + screen_col
    world_y = screen_top_left_y + screen_row
    
    return world_x, world_y
```

### Outcome Detection Logic

```python
def detect_outcome(action, old_pos, new_pos, old_facing, new_facing, old_map, new_map):
    # Map change (highest priority)
    if old_map != new_map:
        return {"type": "map_change", "success": True}
    
    # Movement (position changed)
    if old_pos != new_pos:
        return {"type": "movement", "success": True}
    
    # Turn (facing changed, position same)
    if old_facing != new_facing:
        return {"type": "turn", "success": True}
    
    # Blocked (nothing changed)
    return {"type": "blocked", "success": False}
```

### Traversal Map Update Logic

```python
def update_traversal(outcome, old_pos, new_pos, action):
    if outcome["type"] == "movement":
        # Mark old position as walkable
        set_traversal_at(old_pos, 'W')
        # Mark new position as player
        set_traversal_at(new_pos, 'P')
    
    elif outcome["type"] == "turn":
        # No movement, keep as is (or mark as W if first time)
        set_traversal_at(old_pos, 'W')
    
    elif outcome["type"] == "blocked":
        # Calculate target tile based on action direction
        target = calculate_target_tile(old_pos, action)
        # Mark as blocked
        set_traversal_at(target, 'N')
    
    elif outcome["type"] == "map_change":
        # Mark exit tile as traversal
        set_traversal_at(old_pos, 'T')
```

---

## Testing Utilities

### Manual Testing

```python
# Test memory reading
from modules.llm_trainer.memory_reader import MemoryReader
reader = MemoryReader()
state = reader.read_full_state()
print(state)

# Test vision processing
from modules.llm_trainer.vision_processor import VisionProcessor
vision = VisionProcessor()
data = vision.process_frame()
print(data['tile_map'])

# Test map operations
from modules.llm_trainer.map_manager import MapManager
from pathlib import Path
from modules.context import context

manager = MapManager()
map_data = manager.load_map("Test Map", 3, 0)
manager.set_traversal_at(5, 5, 'W')
manager.save_map()
```

### Viewing Map Files

```bash
# Pretty-print JSON
cat profiles/LLM/llm_trainer/maps/map_3_0.json | python -m json.tool

# Count tiles
cat profiles/LLM/llm_trainer/maps/map_3_0.json | grep '"tree"' | wc -l
```

### Console Debugging

```python
from modules.console import console

# Colored output
console.print("[green]Success![/]")
console.print("[red]Error![/]")
console.print("[yellow]Warning[/]")
console.print("[blue]Info[/]")
console.print("[dim]Debug info[/]")
```

---

## Common Tasks

### Adding a New Traversal Marker

1. Add to `MapManager` class constants:
```python
LEDGE = 'L'  # One-way ledge
```

2. Update handling in outcome detection

3. Update documentation/legend

### Changing Decision Interval

In `llm_trainer.py`:
```python
self.decision_interval = 30  # Frames between decisions
# 30 frames ≈ 0.5 seconds at 60 FPS
```

### Adding New Mock Strategy

In `agent.py`, add to `MockLLM`:
```python
def _my_strategy(self, game_state, vision_data):
    # Your logic here
    return {
        "action": "Up",
        "reasoning": "Custom strategy",
        "confidence": 0.8,
        "strategy": "my_strategy"
    }
```

### Debugging ResNet Issues

```python
# Check if model loaded
if vision.model is None:
    print("Model not loaded!")
else:
    print(f"Model on device: {vision.device}")
    print(f"Classes: {len(vision.class_labels)}")

# Test single tile classification
tile = vision.extract_tiles(cropped)[0]  # First tile
result = vision.classify_tiles_resnet(tile[np.newaxis, ...])
print(f"Tile classified as: {result[0][0]}")
```

---

## Performance Notes

### Current Performance:
- **Vision Processing**: ~0.1s per frame (GPU)
- **Memory Reading**: ~0.001s
- **Map Updates**: ~0.001s
- **Decision Making**: Instant (mock LLM)
- **Overall**: ~3-4 decisions per second

### Bottlenecks:
1. Vision processing (GPU-bound)
2. Waiting for action completion
3. ResNet inference (batch helps)

### Optimizations:
- Batch process tiles (done)
- Cache vision if no movement (done)
- Pre-allocate arrays (done)
- Only process vision when moved (implemented)

---

## Quick Reference Tables

### Traversal Markers
| Marker | Meaning | Set When |
|--------|---------|----------|
| `?` | Unknown | Initial state, never visited |
| `W` | Walkable | Player moved through successfully |
| `N` | Blocked | Player tried to move, was blocked |
| `P` | Player | Current player position |
| `T` | Traversal | Map transition tile |
| `I` | Interactable | NPC/sign (future) |
| `L` | Ledge | One-way movement (Phase 6B) |

### Outcome Types
| Type | Success | Position Changed | Facing Changed |
|------|---------|------------------|----------------|
| movement | ✅ | ✅ | Maybe |
| turn | ✅ | ❌ | ✅ |
| blocked | ❌ | ❌ | ❌ |
| map_change | ✅ | Usually | Maybe |

### Action Case Format
| Correct | Wrong |
|---------|-------|
| `Up` | `UP`, `up` |
| `Down` | `DOWN`, `down` |
| `Left` | `LEFT`, `left` |
| `Right` | `RIGHT`, `right` |
| `A` | `a` |
| `B` | `b` |
| `Start` | `START`, `start` |
| `Select` | `SELECT`, `select` |
| `WAIT` | `wait`, `Wait` |

---

This reference should help you navigate the codebase quickly. Refer to individual files for detailed implementation.
