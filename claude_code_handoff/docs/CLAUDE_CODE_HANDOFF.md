# LLM Pokemon Trainer - Claude Code Handoff

**Date**: February 2, 2026  
**Project**: LLM-powered Pokemon FireRed player using pokebot-gen3  
**Current Phase**: 6A Complete ✅ → Ready for 6B/6C  
**Developer**: Transitioning to Claude Code/Opus

---

## 🎯 Mission

Build an AI agent that plays Pokemon FireRed by:
1. Reading game state from memory
2. Processing screenshots with ResNet vision model
3. Building maps of explored areas
4. Making decisions via LLM
5. Executing actions and learning from outcomes

---

## ✅ What's Been Completed (Phase 6A)

### Working Components:

1. **Memory Reader** (`modules/llm_trainer/memory_reader.py`)
   - Extracts player position, facing, map info from game memory
   - Detects map transitions
   - Reads Pokemon party data

2. **Vision Processor** (`modules/llm_trainer/vision_processor.py`)
   - ResNet-18 model classifies 16x16 tiles into 103 classes
   - Processes 240x160 screenshots → 15x9 tile grids
   - Batch inference with GPU acceleration
   - Real tile names: `tree`, `path`, `building`, `npc_left`, etc.

3. **Action Executor** (`modules/llm_trainer/action_executor.py`)
   - Executes button presses: Up, Down, Left, Right, A, B, Start, Select, WAIT
   - Handles Pokemon movement mechanics (turn vs move)

4. **Agent** (`modules/llm_trainer/agent.py`)
   - Mock LLM with strategies: random, scripted_exit_house, explore
   - Decision tracking and history
   - Ready for real LLM integration

5. **Map Manager** (`modules/llm_trainer/map_manager.py`)
   - Stores tile maps (ResNet classifications) per map area
   - Stores traversal maps (?, W, N, P, T markers)
   - Pre-allocated coordinate grids matching game coords
   - JSON persistence with automatic save/load
   - **VERIFIED WORKING**: See `map_3_0.json` example

6. **Bot Mode** (`modules/modes/llm_trainer.py`)
   - Main orchestrator integrating all components
   - Decision → Action → Outcome loop
   - Periodic map saving
   - Outcome detection (movement, blocked, turn, map_change)

### Verification Results:

**Map Built**: Pallet Town (map_3_0)
- **Tile Map**: 395 tiles classified (tree, path, building, fence, flower_pot, npc, mailbox, sign, door)
- **Traversal Map**: 14 walkable, 6 blocked, 1 player position
- **Bounds**: (0,0) to (13,16)
- **ResNet Accuracy**: Excellent - detecting NPCs, doors, objects correctly

---

## 🚀 Your Mission (Phases 6B-9)

### Phase 6B: Enhanced Outcome Detection (Priority 1)

**Goal**: Improve movement outcome logic and edge case handling

**Tasks**:
1. Fix edge cases in blocked tile detection
2. Handle repeated blocking (don't spam mark same tile)
3. Better turn vs movement detection
4. Handle special movements (ledge jumps, warps)
5. Detect player states (menu, battle, dialogue, frozen)

**Key File**: `modules/modes/llm_trainer.py` (lines 130-180)

**Reference**: FireRed-LLMRL's `overworld_navigator.py` for edge cases

---

### Phase 6C: Map Connectivity Graph (Priority 2)

**Goal**: Link traversal tiles between maps to build world graph

**Tasks**:
1. Calculate entry tile when entering new map
2. Link exit tile (old map) to entry tile (new map)
3. Store bidirectional connections
4. Save connections to `map_connections.json`
5. Provide graph to LLM for navigation

**Key Files**: 
- `modules/llm_trainer/map_manager.py` (add connection methods)
- New file: `modules/llm_trainer/map_graph.py`

**Data Structure**:
```python
{
  "map_3_0": [  # Pallet Town
    {
      "exit_tile": (6, 7),
      "target_map": "map_4_0",
      "entry_tile": (4, 8),
      "direction": "Up"
    }
  ]
}
```

---

### Phase 7: Decision Logging (Priority 3)

**Goal**: Save all decisions to JSON for debugging and training

**Tasks**:
1. Create SessionManager to track sessions
2. Save each decision with full context:
   - Game state (position, map, party)
   - Vision data (tile map, screenshot)
   - LLM reasoning
   - Action executed
   - Outcome result
3. Organize by session ID and timestamp
4. Implement cleanup (keep last N sessions)

**New File**: `modules/llm_trainer/decision_logger.py`

**Storage**: `profiles/<profile>/llm_trainer/sessions/`

---

### Phase 8: HTTP Visualization (Priority 4)

**Goal**: Add web interface for monitoring agent in real-time

**Tasks**:
1. Extend pokebot's HTTP server with new endpoints
2. `/llm/status` - Current agent state
3. `/llm/decisions` - Recent decision history
4. `/llm/maps/<map_key>` - View map JSON
5. `/llm/map-viewer` - Interactive map viewer
6. Live updates via polling or WebSockets

**Files**:
- `modules/http/http_server.py` (extend)
- `modules/http/static/llm/` (new frontend)

---

### Phase 9: Real LLM Integration (Priority 5)

**Goal**: Replace mock LLM with real LLM APIs

**Tasks**:
1. Create LLM provider interfaces:
   - OpenAI (GPT-4)
   - Anthropic (Claude)
   - Google (Gemini)
2. Prompt engineering for Pokemon gameplay
3. Token tracking and cost monitoring
4. Error handling and fallbacks
5. Rate limiting

**New Files**:
- `modules/llm_trainer/llm_providers/openai_provider.py`
- `modules/llm_trainer/llm_providers/anthropic_provider.py`
- `modules/llm_trainer/llm_providers/gemini_provider.py`

---

## 📚 Key Concepts

### Coordinate System

Each map has independent coordinates starting at (0,0):
- **Map 1**: (0,0) to (50,30)
- **Map 2**: (0,0) to (40,25)

Player position uses game's actual coordinates (not screen-relative).

Screen is 15x9 tiles centered on player at (7,4).

### Tile Map vs Traversal Map

**Tile Map**: Names of tiles from ResNet
```
tree tree path path building
tree path path path building
```

**Traversal Map**: Movement status
```
?  ?  W  W  ?
?  W  W  W  ?
```

**Separate storage** - linked by coordinates only.

### Movement Mechanics

Pokemon movement requires understanding:
1. **Turn**: Facing changes, position stays same
2. **Move**: Position changes after facing correct direction
3. **Blocked**: Neither facing nor position changes
4. **Warp**: Map changes (detect via map_name/group/number)

### Map Transitions

When player changes maps:
1. Save old map with exit tile marked as `T`
2. Load/create new map
3. Calculate entry tile based on player position/facing
4. Link exit → entry bidirectionally

Example:
```
House (map_4_0) exit at (4,1) ←→ Town (map_3_0) entry at (6,7)
```

---

## 🗂️ File Structure

```
modules/
├── modes/
│   └── llm_trainer.py              # Main bot mode orchestrator
└── llm_trainer/
    ├── __init__.py
    ├── memory_reader.py             # ✅ Complete
    ├── vision_processor.py          # ✅ Complete
    ├── action_executor.py           # ✅ Complete
    ├── agent.py                     # ✅ Complete (mock)
    ├── map_manager.py               # ✅ Complete (basic)
    ├── decision_logger.py           # ❌ TODO (Phase 7)
    ├── map_graph.py                 # ❌ TODO (Phase 6C)
    └── models/
        ├── best_resnet.pth          # ResNet-18 weights
        └── class_labels_run2.txt    # 103 tile classes
```

**Profiles Directory**:
```
profiles/<profile>/llm_trainer/
├── maps/
│   ├── map_3_0.json                # Pallet Town
│   └── map_4_0.json                # Player's House
├── sessions/                       # TODO: Decision logs
└── map_connections.json            # TODO: World graph
```

---

## 🔧 Development Environment

### Prerequisites:
- Python 3.10+
- PyTorch with CUDA (for ResNet)
- pokebot-gen3 installed

### Key Dependencies:
```python
torch
torchvision
numpy
```

### Running the Bot:
```bash
cd pokebot-gen3
conda activate pokebot
python pokebot.py LLM -na --bot-mode LLM Trainer
# Select "LLM Trainer" mode
```

### Testing Individual Components:
```python
# Test Memory Reader
from modules.llm_trainer.memory_reader import MemoryReader
reader = MemoryReader()
state = reader.read_full_state()

# Test Vision Processor
from modules.llm_trainer.vision_processor import VisionProcessor
vision = VisionProcessor()
data = vision.process_frame()

# Test Map Manager
from modules.llm_trainer.map_manager import MapManager
manager = MapManager()
manager.load_map("Test", 3, 0)
```

---

## 📋 Implementation Priorities

### Week 1: Phase 6B + 6C
- **Day 1-2**: Enhanced outcome detection
- **Day 3-4**: Map connectivity graph
- **Day 5**: Testing and bug fixes

### Week 2: Phase 7 + 8
- **Day 1-2**: Decision logging system
- **Day 3-4**: HTTP visualization endpoints
- **Day 5**: Frontend map viewer

### Week 3: Phase 9
- **Day 1-3**: LLM provider integration
- **Day 4-5**: Prompt engineering and testing

---

## ⚠️ Known Issues & Edge Cases

### Current Bugs:
1. **"No map data to save"** on first run - harmless but annoying
2. **Repeated blocked marking** - same tile marked multiple times
3. **No state detection** - can't detect menus/battles/dialogue

### Edge Cases to Handle:
1. **Ledge jumps** - One-way movement (can jump down, can't go back up)
2. **NPCs blocking paths** - Marked as blocked, but may move
3. **Scripted events** - Player frozen during cutscenes
4. **Warps** - Position changes dramatically (caves, buildings)
5. **Multi-tile movements** - Surfing, biking, running shoes

---

## 📖 Reference Materials

### Original Project:
- **FireRed-LLMRL**: Previous implementation (uploaded files) (also found in C:\Users\josea\pokebot\pokebot-gen3\reference_material)
  - `overworld_navigator.py` - Edge case handling
  - `overworld_mapper.py` - Map system reference
  - `resnet_vision_tool.py` - Vision pipeline

### pokebot-gen3 APIs:
- `context.emulator.press_button(button)` - Execute actions
- `context.emulator.get_screenshot()` - Get PIL Image
- `get_player_avatar()` - Player position/facing
- `get_map_data_for_current_position()` - Map info
- `get_game_state()` - Game state enum (menu, battle, overworld)

### Design Documents:
- `LLM_TRAINER_DESIGN.md` - Full architecture
- `IMPLEMENTATION_GUIDE.md` - Step-by-step phases
- `PHASE_6A_SUMMARY.md` - What's complete
- `NEXT_PHASES.md` - Detailed 6B/6C/7/8/9 instructions

---

## 🎯 Success Criteria

### Phase 6B Complete:
- [ ] Blocked tiles not marked repeatedly
- [ ] Turn vs move detection 100% accurate
- [ ] Player state detection (menu, battle, dialogue)
- [ ] Ledge jump handling
- [ ] Warp detection

### Phase 6C Complete:
- [ ] Map connections stored in JSON
- [ ] Bidirectional links work
- [ ] Entry tile calculation correct
- [ ] Graph queryable by agent
- [ ] Multiple map transitions tested

### Phase 7 Complete:
- [ ] Every decision logged to JSON
- [ ] Sessions organized by timestamp
- [ ] Full context saved (state + vision + reasoning + outcome)
- [ ] Cleanup mechanism works
- [ ] Logs readable and parseable

### Phase 8 Complete:
- [ ] HTTP endpoints respond correctly
- [ ] Map viewer displays tile/traversal maps
- [ ] Decision history visible
- [ ] Live updates work
- [ ] Mobile-friendly UI

### Phase 9 Complete:
- [ ] OpenAI provider working
- [ ] Anthropic provider working
- [ ] Gemini provider working
- [ ] Prompts optimized for gameplay
- [ ] Token tracking accurate
- [ ] Cost monitoring implemented

---

## 🤝 Communication

### Questions?
- Check design docs first
- Review FireRed-LLMRL code for examples C:\Users\josea\pokebot\pokebot-gen3\reference_material)
- Test incrementally (don't build everything at once)

### Reporting Progress:
For each phase:
1. Implementation summary
2. Testing results
3. Any blockers or questions
4. Suggested improvements

### Code Quality:
- Type hints for all functions
- Docstrings for public methods
- Error handling with try/except
- Console logging for debugging
- Save frequently during development

---

## 🚀 Getting Started

1. **Read All Handoff Docs** (this + PHASE_6A_SUMMARY + NEXT_PHASES)
2. **Review Existing Code** (understand what's built)
3. **Test Phase 6A** (verify it works on your machine)
4. **Start Phase 6B** (enhanced outcomes)
5. **Iterate and Test** (small changes, frequent testing)

---

## 📁 Attached Files

Include these in Claude Code context:
1. All handoff markdown documents
2. Current codebase:
   - `modules/modes/llm_trainer.py`
   - `modules/llm_trainer/*.py`
3. Example outputs:
   - `map_3_0.json`
   - Console logs
4. Reference code:
   - `overworld_navigator.py`
   - `overworld_mapper.py`
   - `resnet_vision_tool.py`

---

**Good luck! The foundation is solid. Time to build the intelligence layer.** 🧠🎮
