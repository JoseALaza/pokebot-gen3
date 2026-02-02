# Testing Guide - LLM Trainer

Comprehensive testing procedures for each development phase.

---

## General Testing Principles

### 1. Test Early, Test Often
- Test each method individually before integration
- Run bot after every significant change
- Keep test sessions short (5-10 minutes)

### 2. Incremental Testing
- Don't build everything then test
- Test one feature, verify, move to next
- Easier to debug when you know what just changed

### 3. Save Often
- Maps auto-save every 10 decisions
- But manually save before risky changes
- Keep backups of working states

### 4. Console is Your Friend
- Watch console output carefully
- Add debug prints liberally
- Use colors to highlight important info

---

## Phase 6A Testing (Complete ✅)

### Verification Checklist

#### ResNet Model
- [ ] Model file exists: `modules/llm_trainer/models/best_resnet.pth`
- [ ] Class labels exist: `modules/llm_trainer/models/class_labels_run2.txt`
- [ ] Model loads without errors
- [ ] CUDA/CPU device detected correctly
- [ ] Console shows: "ResNet-18 model loaded successfully (103 classes)"

**Test**:
```python
from modules.llm_trainer.vision_processor import VisionProcessor
vision = VisionProcessor()
assert vision.model is not None
assert len(vision.class_labels) == 103
print(f"Device: {vision.device}")
```

#### Vision Processing
- [ ] Screenshot captured correctly
- [ ] Tiles extracted (9×15 grid)
- [ ] Classifications return real tile names (not "unknown")
- [ ] Tile map matches what's visible in game
- [ ] No crashes during processing

**Test**:
```python
vision = VisionProcessor()
data = vision.process_frame()
print(f"Tiles: {data['tiles_x']} x {data['tiles_y']}")
print(f"Sample tiles: {data['tile_map'][4]}")  # Center row
# Should see: ['path', 'building', 'tree', ...] not ['unknown', ...]
```

#### Map Manager
- [ ] Maps directory created
- [ ] New map creates JSON file
- [ ] Tile map updates with screen tiles
- [ ] Traversal map marks W/N/P correctly
- [ ] Bounds expand as player explores
- [ ] Save/load works correctly

**Test**:
```python
from modules.llm_trainer.map_manager import MapManager
manager = MapManager()
manager.load_map("Test", 3, 0)
manager.set_traversal_at(5, 5, 'W')
manager.save_map()
# Check JSON file exists and contains marker
```

#### Outcome Detection
- [ ] Movement detected (position changes)
- [ ] Turns detected (facing changes)
- [ ] Blocked detected (nothing changes)
- [ ] Map changes detected
- [ ] Correct tiles marked in traversal map

**Test in Game**:
1. Start bot
2. Let it move successfully → Check for ✓ and "Moved from..."
3. Let it hit wall → Check for ✗ and "blocked by obstacle"
4. Watch console for "Marked tile (X, Y) as BLOCKED"

#### Integration
- [ ] Bot mode starts without errors
- [ ] All components initialize
- [ ] Main loop runs smoothly
- [ ] Decisions made every ~0.5 seconds
- [ ] No memory leaks over time

**Test**:
Run bot for 100+ decisions, watch for:
- Memory usage stable
- FPS stable
- No error messages
- Maps saving periodically

---

## Phase 6B Testing (Enhanced Outcomes)

### Test 1: Repeated Blocking Prevention

**Setup**:
1. Position player facing a wall
2. Let bot try to move into wall repeatedly

**Expected**:
```
✗ Decision # 10: Up | Position: (4, 8) | Facing: Up
  → Could not move Up - blocked by obstacle
  → Marked tile (4, 7) as BLOCKED

✗ Decision # 11: Up | Position: (4, 8) | Facing: Up
  → Could not move Up - blocked by obstacle
  → Tile (4, 7) already marked as blocked  ← This!

✗ Decision # 12: Up | Position: (4, 8) | Facing: Up
  → Could not move Up - blocked by obstacle
  → Tile (4, 7) already marked as blocked  ← Again!
```

**Verify**:
- [ ] First attempt marks tile as 'N'
- [ ] Subsequent attempts don't re-mark
- [ ] Console shows "already marked" message
- [ ] `last_blocked_tile` tracked correctly
- [ ] Reset on successful movement

### Test 2: Turn vs Movement Detection

**Setup**:
1. Player at (5, 5) facing Up
2. Agent decides: "Right"
3. Player turns Right (doesn't move)

**Expected**:
```
✓ Decision # 5: Right | Position: (5, 5) | Facing: Right
  → Changing direction from Up to Right
  → Outcome: Turned from Up to Right
```

**Verify**:
- [ ] Outcome type is "turn"
- [ ] Position didn't change
- [ ] Facing changed
- [ ] No tiles marked as blocked
- [ ] Old position marked as W (or kept as is)

### Test 3: Player State Detection

**Setup**:
1. Run bot normally
2. Open menu manually (Start button)
3. Watch bot response

**Expected**:
```
[yellow]In menu. Pressing B to exit.[/]
```

**Verify**:
- [ ] Bot detects menu state
- [ ] Presses B to close menu
- [ ] Waits for menu to close
- [ ] Resumes normal operation

**Repeat for**:
- [ ] Battle encounter
- [ ] Dialogue with NPC

### Test 4: Ledge Jump Detection

**Setup**:
1. Position player on a ledge
2. Let player jump down

**Expected**:
```
[magenta]Detected multi-tile movement! Distance: 2[/]
✓ Decision # 20: Down | Position: (5, 7) | Facing: Down
  → Moved from (5, 5) to (5, 7)
  → Outcome: Moved 2 tiles
```

**Verify**:
- [ ] Distance > 1 detected
- [ ] Old tile marked as 'L' (ledge)
- [ ] New tile marked as 'W'
- [ ] Console shows multi-tile movement message

### Test 5: Warp/Door Detection

**Setup**:
1. Walk through a door

**Expected**:
```
[magenta]Map transition: Pallet Town (6,7) → Player's House (4,8)[/]
✓ Decision # 15: Up | Position: (4, 8) | Facing: Up
  → Outcome: Changed map: Pallet Town → Player's House
```

**Verify**:
- [ ] Old map saved with exit tile as 'T'
- [ ] New map loaded
- [ ] Entry tile calculated correctly
- [ ] Console shows transition details

---

## Phase 6C Testing (Map Connectivity)

### Test 1: Simple Connection

**Setup**:
1. Fresh start (delete map_connections.json)
2. Exit house to town

**Expected**:
```
[magenta]Added connection: map_4_0 (4,1) → map_3_0 (6,7)[/]
```

**Verify**:
- [ ] Connection added to graph
- [ ] Both directions stored (bidirectional)
- [ ] `map_connections.json` created
- [ ] JSON structure correct:
```json
{
  "map_4_0": [{
    "from_map": "map_4_0",
    "from_tile": [4, 1],
    "to_map": "map_3_0",
    "to_tile": [6, 7],
    "direction": "Down"
  }],
  "map_3_0": [{
    "from_map": "map_3_0",
    "from_tile": [6, 7],
    "to_map": "map_4_0",
    "to_tile": [4, 1],
    "direction": "Up"
  }]
}
```

### Test 2: Multiple Connections

**Setup**:
1. Visit 4+ different maps
2. Create multiple connections

**Expected**:
- [ ] All connections stored
- [ ] No duplicates
- [ ] Bidirectional links maintained

**Verify**:
```python
from modules.llm_trainer.map_graph import MapGraph
from pathlib import Path

graph = MapGraph(Path("profiles/LLM/llm_trainer"))
connections = graph.get_connections("map_3_0")
print(f"Pallet Town has {len(connections)} connections")
for conn in connections:
    print(f"  → {conn.to_map} at {conn.to_tile}")
```

### Test 3: Pathfinding

**Setup**:
1. Create connections: A ↔ B ↔ C ↔ D
2. Test pathfinding from A to D

**Expected**:
```python
path = graph.find_path("map_A", "map_D")
assert path == ["map_A", "map_B", "map_C", "map_D"]
```

**Verify**:
- [ ] BFS finds shortest path
- [ ] Returns correct sequence
- [ ] Handles no-path case (returns None)
- [ ] Handles same-map case (returns [map])

### Test 4: Re-entry (No Duplicate)

**Setup**:
1. Exit house (creates connection)
2. Re-enter house
3. Exit again

**Expected**:
- [ ] Connection not duplicated
- [ ] Existing connection reused
- [ ] No errors

---

## Phase 7 Testing (Decision Logging)

### Test 1: Session Creation

**Setup**:
1. Start bot
2. Check session directory

**Expected**:
```
profiles/LLM/llm_trainer/sessions/
└── session_20260202_014437/
    └── metadata.json
```

**Verify**:
- [ ] Session directory created
- [ ] metadata.json exists
- [ ] Session ID correct format
- [ ] Start time recorded

### Test 2: Decision Logging

**Setup**:
1. Run bot for 10 decisions
2. Check session directory

**Expected**:
```
session_20260202_014437/
├── metadata.json
├── decision_0001.json
├── decision_0002.json
├── ...
└── decision_0010.json
```

**Verify**:
- [ ] One JSON file per decision
- [ ] Sequential numbering
- [ ] Each file contains:
  - [ ] Game state before
  - [ ] Vision data (tile map)
  - [ ] Decision (action, reasoning)
  - [ ] Execution success
  - [ ] Outcome

**Sample decision_0001.json**:
```json
{
  "decision_number": 1,
  "timestamp": "2026-02-02T01:44:40.123",
  "frame": 30,
  "game_state_before": {...},
  "vision_data": {"tile_map": [[...]]},
  "decision": {"action": "Up", "reasoning": "..."},
  "execution": {"success": true},
  "outcome": {"type": "movement", "success": true, ...}
}
```

### Test 3: Session End

**Setup**:
1. Stop bot gracefully

**Expected**:
- [ ] `end_time` set in metadata
- [ ] `total_decisions` updated
- [ ] All files saved

### Test 4: Session Cleanup

**Setup**:
1. Create 100+ sessions
2. Trigger cleanup

**Expected**:
- [ ] Old sessions deleted
- [ ] Recent N sessions kept
- [ ] No errors

---

## Phase 8 Testing (HTTP Visualization)

### Test 1: Endpoints Available

**Setup**:
1. Start bot with HTTP server
2. Check endpoints

**Test URLs**:
```bash
curl http://localhost:8888/llm/status
curl http://localhost:8888/llm/decisions
curl http://localhost:8888/llm/maps/map_3_0
```

**Expected**:
- [ ] All endpoints return 200 OK
- [ ] JSON responses valid
- [ ] No CORS errors (if accessing from browser)

### Test 2: Status Endpoint

**URL**: `/llm/status`

**Expected Response**:
```json
{
  "active": true,
  "total_decisions": 42,
  "current_map": "map_3_0",
  "current_position": [6, 8],
  "facing": "Up",
  "last_action": "Up",
  "last_outcome": "blocked",
  "agent_strategy": "explore",
  "maps_explored": 2
}
```

**Verify**:
- [ ] Status reflects current state
- [ ] Updates in real-time

### Test 3: Decisions Endpoint

**URL**: `/llm/decisions?limit=10`

**Expected Response**:
```json
{
  "decisions": [
    {
      "number": 42,
      "action": "Up",
      "outcome": "blocked",
      "timestamp": "..."
    },
    ...
  ]
}
```

**Verify**:
- [ ] Returns recent decisions
- [ ] Limit parameter works
- [ ] Ordered by recency

### Test 4: Map Viewer

**URL**: `/llm/map-viewer`

**Expected**:
- [ ] HTML page loads
- [ ] Map grid displays
- [ ] Tile names shown
- [ ] Traversal markers colored:
  - Green: W (walkable)
  - Red: N (blocked)
  - Blue: P (player)
  - Yellow: T (traversal)
- [ ] Updates via polling

---

## Phase 9 Testing (Real LLM Integration)

### Test 1: Provider Initialization

**Test OpenAI**:
```python
from modules.llm_trainer.llm_providers.openai_provider import OpenAIProvider

provider = OpenAIProvider(api_key="sk-...")
assert provider.is_available()
```

**Verify**:
- [ ] API key loaded correctly
- [ ] Connection test succeeds
- [ ] Error handling for invalid key

**Repeat for**:
- [ ] Anthropic
- [ ] Gemini

### Test 2: Decision Making

**Setup**:
1. Replace mock LLM with real LLM
2. Make one decision

**Expected**:
```
[blue]Calling OpenAI GPT-4...[/]
[green]Received decision: Up (confidence: 0.85)[/]
[dim]Reasoning: There's a path to the north that hasn't been explored[/]
```

**Verify**:
- [ ] LLM called successfully
- [ ] Decision returned in correct format
- [ ] Reasoning makes sense
- [ ] Confidence score reasonable
- [ ] Action is valid

### Test 3: Token Tracking

**Setup**:
1. Make 10 decisions
2. Check token usage

**Expected**:
```
[cyan]Token usage this session:[/]
  Prompt tokens: 12,450
  Completion tokens: 890
  Total tokens: 13,340
  Estimated cost: $0.27
```

**Verify**:
- [ ] Tokens counted correctly
- [ ] Cost calculated (if available)
- [ ] Logged to file

### Test 4: Error Handling

**Test Cases**:

**Rate Limit**:
- [ ] Exponential backoff works
- [ ] Max retries respected
- [ ] Falls back to mock if exhausted

**Invalid Response**:
- [ ] Malformed JSON handled
- [ ] Missing fields detected
- [ ] Fallback decision made

**Network Error**:
- [ ] Timeout handled
- [ ] Retry logic works
- [ ] Error logged

### Test 5: Prompt Engineering

**Setup**:
1. Test with different prompt templates
2. Compare decision quality

**Metrics**:
- [ ] Decisions make sense given context
- [ ] LLM understands Pokemon mechanics
- [ ] Reasoning is coherent
- [ ] Actions align with stated goals

---

## Integration Testing

### Test 1: Full Pipeline (6A → 9)

**Scenario**: Play for 30 minutes

**Verify All Phases Work Together**:
- [ ] Maps build correctly
- [ ] Connections tracked
- [ ] Decisions logged
- [ ] HTTP updates live
- [ ] LLM makes good decisions
- [ ] No crashes
- [ ] Performance acceptable

### Test 2: Edge Cases

**Test All Known Edge Cases**:
- [ ] Ledge jumps
- [ ] Warps
- [ ] NPCs blocking
- [ ] Battles
- [ ] Menus
- [ ] Scripted events
- [ ] Multi-tile movements

### Test 3: Long-Running Stability

**Run for 2+ hours**:
- [ ] No memory leaks
- [ ] No performance degradation
- [ ] Maps don't corrupt
- [ ] Decision logs don't overflow
- [ ] HTTP stays responsive

---

## Debugging Techniques

### When Things Go Wrong

#### Bot Crashes

1. **Check console output** - Last message before crash
2. **Check Python error** - Traceback shows which file/line
3. **Add debug prints** - Around suspected area
4. **Simplify** - Remove recent changes one by one

#### Wrong Behavior

1. **Watch console carefully** - What's being logged?
2. **Check map JSON** - Is data correct?
3. **Test component in isolation** - Memory? Vision? Agent?
4. **Add assertions** - Verify assumptions

#### Performance Issues

1. **Profile code** - Find bottleneck
2. **Check GPU usage** - Is ResNet running on GPU?
3. **Reduce decision interval** - Slower = less CPU
4. **Disable vision** - Temporarily use mock data

### Useful Debug Code

```python
# Pause bot to inspect state
import pdb; pdb.set_trace()

# Print current state
print(f"Position: {game_state['player']['position']}")
print(f"Map: {game_state['player']['map']}")

# Check map data
import json
with open("profiles/LLM/llm_trainer/maps/map_3_0.json") as f:
    data = json.load(f)
    print(f"Bounds: {data['bounds']}")
    print(f"Explored: {len([m for row in data['traversal_map'] for m in row if m != '?'])}")

# Watch for specific tile
if (player_x, player_y) == (6, 7):
    console.print("[bold red]AT SPECIAL LOCATION![/]")
```

---

## Test Data Sets

### Minimal Test (5 minutes)
- **Purpose**: Quick verification
- **Actions**: ~50 decisions
- **Maps**: 1-2 maps
- **Expected**: No crashes, basic features work

### Standard Test (30 minutes)
- **Purpose**: Comprehensive testing
- **Actions**: ~300 decisions
- **Maps**: 4-5 maps
- **Expected**: All features work, edge cases handled

### Stress Test (2+ hours)
- **Purpose**: Stability and performance
- **Actions**: ~2000+ decisions
- **Maps**: 10+ maps
- **Expected**: No degradation, no leaks

---

## Automated Testing (Future)

### Unit Tests

```python
# test_memory_reader.py
def test_get_player_state():
    reader = MemoryReader()
    state = reader.get_player_state()
    assert 'x' in state['position']
    assert 'y' in state['position']
    assert state['facing'] in ['Up', 'Down', 'Left', 'Right']

# test_vision_processor.py
def test_tile_extraction():
    vision = VisionProcessor()
    screenshot = np.zeros((160, 240, 3), dtype=np.uint8)
    cropped = vision.crop_screenshot(screenshot)
    tiles = vision.extract_tiles(cropped)
    assert tiles.shape == (135, 16, 16, 3)

# test_map_manager.py
def test_coordinate_calculation():
    manager = MapManager()
    target = manager.calculate_target_tile(5, 5, "Up")
    assert target == (5, 4)
```

### Integration Tests

```python
# test_integration.py
def test_full_pipeline():
    """Test decision → action → outcome loop"""
    # Setup
    mode = LLMTrainerMode()
    
    # Run one decision
    generator = mode.run()
    for _ in range(100):  # Run for 100 frames
        next(generator)
    
    # Verify
    assert mode.agent.get_decision_count() > 0
    assert mode.map_manager.current_map_data is not None
```

---

## Continuous Testing Checklist

Before each commit:
- [ ] Code runs without errors
- [ ] No new console warnings
- [ ] Bot still makes decisions
- [ ] Maps still save correctly
- [ ] Tests pass (if written)

Before each pull request:
- [ ] All phases tested
- [ ] Edge cases handled
- [ ] Performance acceptable
- [ ] Documentation updated
- [ ] Clean git history

---

**Testing is not optional. Test early, test often, test thoroughly.** ✅
