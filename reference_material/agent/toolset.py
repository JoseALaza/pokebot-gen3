# src/agent/toolset.py
import logging
import json
import uuid

class Toolset:
    """
    Defines function schemas for function calling, plus code
    to handle them at runtime.  Prompt text lives elsewhere.
    """

    # ------------------------------------------------------------------
    # Canonical-button helpers / constants
    # ------------------------------------------------------------------
    _VALID_BTNS = {
        "A", "B", "Up", "Down", "Left", "Right",
        "L", "R", "Start", "Select"
    }

    @staticmethod
    def _canonical_button(val: str) -> str:
        """
        Normalise “a” → “A”, “left” → “Left”, etc.
        Returns val unchanged if not a str.
        """
        if not isinstance(val, str):
            return val
        txt = val.strip()
        if not txt:
            return val
        if len(txt) == 1:
            return txt.upper()
        lower = txt.lower()
        if lower in {"start", "select"}:
            return lower.title()
        return txt.capitalize()

    # ------------------------------------------------------------------
    def __init__(self, emulator, memory_mgr):
        self.emulator   = emulator
        self.memory_mgr = memory_mgr
        self.logger     = logging.getLogger(__name__)

    # ------------------------------------------------------------------
    #  Tool schemas sent to the LLM
    # ------------------------------------------------------------------
    def get_tool_schemas(self, flag:str):
        if flag.upper() == "OVERWORLD":
            return [
                self._move_player_schema(),
                self._turn_player_schema(),
                self._player_interact_schema(),
                self._write_to_memory_schema(),
                self._update_goal_schema(),
                self._overworld_navigator_schema()
            ]
        return [
            self._press_gba_button_schema(),
            self._write_to_memory_schema(),
            self._update_goal_schema(),
        ]

    # ―――  press_gba_button  ―――
    def _press_gba_button_schema(self):
        return {
            "type": "function",
            "function": {
                "name": "press_gba_button",
                "description": """
                press_gba_button(button: str): Executes a single button press on the Game Boy Advance. This command can be used for:

                1.  **Menu Navigation and Selection:** This command can be used to navigate menus, select options, and confirm actions within the game.

                **Important Notes:**

                * The `button` parameter must be a valid GBA button: 'A', 'B', 'Up', 'Down', 'Left', or 'Right'.
                """,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "button": {
                            "type": "string",
                            "enum": list(self._VALID_BTNS),
                            "description": "Which button to press (A, B, Up, Down, Left, Right, L, R, Start, Select)."
                        }
                    },
                    "required": ["button"],
                    "additionalProperties": False
                },
                "strict": True
            }
        }

    def _move_player_schema(self):
        return {
            "type": "function",
            "function": {
                "name": "move_player",
                "description": """
                move_player(button: str): Executes a player movement on the Game Boy Advance. This command can be used for:

                1.  **Player Movement:** When the player is in an overworld environment, this command can move the player one tile in the direction they are currently facing.

                **Important Notes:**

                * The `button` parameter must be a valid GBA direction: 'Up', 'Down', 'Left', or 'Right'.
                """,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "button": {
                            "type": "string",
                            "enum": list(self._VALID_BTNS),
                            "description": "Which direction to travel (Up, Down, Left, Right)."
                        }
                    },
                    "required": ["button"],
                    "additionalProperties": False
                },
                "strict": True
            }
        }
        
    def _turn_player_schema(self):
        return {
            "type": "function",
            "function": {
                "name": "turn_player",
                "description": """
                turn_player(button: str): Executes a change to player facing direction on the Game Boy Advance. This command can be used for:

                1.  **Player Facing Adjustment:** If the player is not facing the desired  direction, this command will rotate the player to face that direction.

                **Important Notes:**

                * The `button` parameter must be a valid GBA direction: 'Up', 'Down', 'Left', or 'Right'.
                """,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "button": {
                            "type": "string",
                            "enum": list(self._VALID_BTNS),
                            "description": "Which direction to face (Up, Down, Left, Right)."
                        }
                    },
                    "required": ["button"],
                    "additionalProperties": False
                },
                "strict": True
            }
        }
        
    def _player_interact_schema(self):
        return {
            "type": "function",
            "function": {
                "name": "player_interact",
                "description": """
                player_interact(button: str): Executes a single button press on the Game Boy Advance. This command can be used for:

                1.  **Player Interaction:** When the player is in an overworld environment, this command can let the player interact with the tile they are currently facing.

                **Important Notes:**

                * The `button` parameter must be a valid GBA button: 'A', 'B', 'Start', or 'Select'.
                """,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "button": {
                            "type": "string",
                            "enum": list(self._VALID_BTNS),
                            "description": "Which button to press (A, B, L, R, Start, Select)."
                        }
                    },
                    "required": ["button"],
                    "additionalProperties": False
                },
                "strict": True
            }
        }

    # ―――  write_to_memory  ―――
    def _write_to_memory_schema(self):
        return {
            "type": "function",
            "function": {
                "name": "write_to_memory",
                "description":  "Persist a fact to the **Knowledge-Base**. "
                                +"The key will be autogenerated; pass a short, self-contained statement. "
                                +"Use this for stable information you might need in future iterations.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "The text to add to the knowledge base. lessons learned, notes, important observations, etc."
                        }
                    },
                    "required": ["text"],
                    "additionalProperties": False
                },
                "strict": True
            }
        }

    # ―――  update_goal  ―――
    def _update_goal_schema(self):
        return {
            "type": "function",
            "function": {
                "name": "update_goal",
                "description": "Add or remove a goal from the agent's goals list.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": ["add", "remove"],
                            "description": "Whether to add or remove the goal"
                        },
                        "goal_text": {
                            "type": "string",
                            "description": "The text of the goal to add or remove."
                        }
                    },
                    "required": ["action", "goal_text"],
                    "additionalProperties": False
                },
                "strict": True
            }
        }

    # ―――  overworld_navigator  ―――
    def _overworld_navigator_schema(self):
        return {
            "type": "function",
            "function": {
                "name": "overworld_navigator",
                "description": """
                overworld_navigator(destination: tuple): Initiates pathfinding and movement to a specified XY coordinate within the overworld.

                **Functionality:**

                * This function utilizes the A* pathfinding algorithm to calculate and execute the optimal route from the player's current position to the `destination` coordinate.
                * It automatically handles all necessary button presses and internal game flags to navigate the player.
                * This command is suitable for both short and long-distance travel within the overworld.
                * The player should primarily rely on the `tile_map` data to determine the desired destination coordinate.

                **Important Notes:**

                * The map coordinate system is X-Y based, with (0, 0) representing the top-left corner of the map.
                * The `overworld_navigator` function can be called repeatedly to travel to the same destination or to different locations. The pathfinding algorithm will always recalculate the optimal route based on the current player position and destination.
                * It is designed to handle pathfinding around most obstacles and game-specific navigation challenges.
                * This function is preferred over press_gba_button for movement of 2 or more tiles.
                """,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "destination_x": {"type": "number"},
                        "destination_y": {"type": "number"}
                    },
                    "required": ["destination_x", "destination_y"],
                    "additionalProperties": False
                },
                "strict": True
            }
        }

    # ------------------------------------------------------------------
    #  Dispatcher
    # ------------------------------------------------------------------
    def handle_single_function_call(
        self,
        general_perception,
        tool_call_instruction: dict, # This is a single call object like {"name": "...", "arguments": "..."}
        internal_thoughts: str,
        short_context: str,
        mapper, # Passed from MainAgent
        navigator # Passed from MainAgent
    ):
        """
        Execute a single tool call.
        If the call interacts with the game world and generates perception data, return that data.
        If the call is internal (e.g., memory update) and doesn't require immediate perception, return None.
        If a call fails, return {"tool_error": {...}}.
        """
        func_name = tool_call_instruction.get("name")
        # The 'arguments' field from ModelManager should already be a JSON string
        raw_args = tool_call_instruction.get("arguments", "{}")
        try:
            args = raw_args if isinstance(raw_args, dict) else json.loads(raw_args)
        except Exception as e:
            self.logger.error(
                f"Failed to parse arguments for {func_name}: {raw_args}. Error: {e}"
            )
            return {
                "tool_error": {
                    "name": func_name,
                    "reason": f"json_parse_error: {e}",
                    "arguments": raw_args,
                }
            }

        if func_name == "press_gba_button":
            # This handler calls general_perception.analyze_images_and_reasoning
            # and returns a perception_blk dictionary
            return self._handle_press_button(
                args, internal_thoughts, short_context,
                general_perception, mapper
            )
        elif func_name == "write_to_memory":
            self._handle_write_to_memory(args)
            return None # Signifies no perception update needed from this tool
        elif func_name == "update_goal":
            self._handle_update_goal(args)
            return None # Signifies no perception update needed from this tool
        elif func_name == "overworld_navigator":
            # This handler calls general_perception.analyze_images_and_reasoning (potentially multiple times)
            # and returns a perception_blk dictionary (e.g., from the last step)
            return self._handle_overworld_nav(
                args, internal_thoughts, short_context,
                general_perception, mapper, navigator
            )
        elif func_name == "move_player":
            return self._handle_move_player(
                args, internal_thoughts, short_context, general_perception, mapper, navigator
            )
        elif func_name == "turn_player":
            return self._handle_turn_player(
                args, internal_thoughts, short_context, general_perception, mapper
            )
        elif func_name == "player_interact":
            return self._handle_player_interact(
                args, internal_thoughts, short_context, general_perception, mapper
            )
        else:
            self.logger.warning(f"Unknown tool function called: {func_name}")
            return {"tool_error": {"name": func_name, "reason": "unknown_tool"}}

    # ------------------------------------------------------------------
    #  press_gba_button handler with canonicalisation + retry meta
    # ------------------------------------------------------------------
    def _handle_press_button(
        self,
        args,
        internal_thoughts: str,
        short_context: str,
        general_perception,
        mapper
    ):
        # auto-normalise casing
        raw       = args.get("button", "A")
        retry_cnt = args.get("_retry", 0)
        button    = self._canonical_button(raw)

        if button not in self._VALID_BTNS:
            if retry_cnt < 2:
                self.logger.warning(
                    f"Invalid BTN '{raw}' → retry {retry_cnt+1}/3"
                )
                return {"tool_error": {
                    "name": "press_gba_button",
                    "reason": f"invalid_button:{raw}",
                    "retry_payload": json.dumps(
                        {"button": "A", "_retry": retry_cnt + 1}
                    )
                }}
            # after three failures—log and give up
            self.memory_mgr.update_context(
                f"[ERROR] press_gba_button failed 3× for '{raw}'."
            )
            return {"tool_error": {
                "name": "press_gba_button",
                "reason": "permanent_invalid"
            }}

        self.logger.info(f"(Tool) press_gba_button => pressing {button}")

        try:
            ga, oa, flag, shots, req, raw_resp = \
                general_perception.analyze_images_and_reasoning(
                    emulator=self.emulator,
                    button=button,
                    main_agent_move_reasoning=internal_thoughts,
                    short_context=short_context
                )
        except Exception as e:
            self.memory_mgr.update_context(f"[ERROR] {e}")
            return {"tool_error": {"name": "press_gba_button",
                                   "reason": str(e)}}

        # # persist perception summary
        self.memory_mgr.update_context(f"[PERCEPTION] {ga}")

        return {
            "prompt_dict": {"note": "See PerceptionAgent code"},
            "request_payload": req,
            "raw_response":  raw_resp,
            "general_analysis": ga,
            "overworld_analysis": oa,
            "game_state_flag": flag,
            "screenshots": shots
        }

    # ------------------------------------------------------------------
    #  Other tool handlers (no behavioural change)
    # ------------------------------------------------------------------
    def _handle_write_to_memory(self, args):
        txt = args.get("text", "")
        # seconds-based keys collide when many writes happen in the same second
        key = f"toolnote_{uuid.uuid4().hex[:8]}"             # 8-char id
        self.memory_mgr.write_kb(key, txt)
        self.logger.info(f"(Tool) write_to_memory ⇒ {key}")

    def _handle_update_goal(self, args):
        if args["action"] == "add":
            self.memory_mgr.add_goal(args["goal_text"])
        else:
            self.memory_mgr.remove_goal(args["goal_text"])
        self.logger.info(f"(Tool) update_goal => {args['action']} '{args['goal_text']}'")

    def _handle_overworld_nav(
        self, args, internal_thoughts, short_context,
        general_perception, mapper, navigator
    ):
        x, y = args.get("destination_x", 0), args.get("destination_y", 0)
        self.logger.info(f"(Tool) overworld_navigator => ({x},{y})")
        mapper.update()
        mapper.save_all_maps()
        moves = navigator.return_directions(x, y)
        if not isinstance(moves, list):
            self.memory_mgr.update_context(f"[PERCEPTION] {moves}")
            return {"tool_error": {"name": "overworld_navigator",
                                   "reason": moves}}
        return navigator.execute_moves(moves, internal_thoughts, short_context)

    def _handle_move_player(self, args, internal_thoughts: str, short_context: str, general_perception, mapper, navigator):
        move = args.get("button", "Up")
        move_direction = {
            "Up": (0, -1),
            "Down": (0, 1),
            "Left": (-1, 0),
            "Right": (1, 0)
        }
        
        # Call Mapper to update the map before any execution
        mapper.update()
        mapper.save_all_maps()
        
        updated_map_data, updated_x, updated_y, updated_facing = mapper.get_player_pos()
        
        x = updated_x + move_direction[move][0]
        y = updated_y + move_direction[move][1]
        
        moves = navigator.return_directions(x, y)
        if not isinstance(moves, list):
            self.memory_mgr.update_context(f"[PERCEPTION] {moves}")
            return {"tool_error": {"name": "overworld_navigator",
                                   "reason": moves}}
        return navigator.execute_moves(moves, internal_thoughts, short_context)
    
    def _handle_turn_player(self, args, internal_thoughts: str, short_context: str, general_perception, mapper):
        # auto-normalise casing
        raw       = args.get("button", "A")
        retry_cnt = args.get("_retry", 0)
        button    = self._canonical_button(raw)

        if button not in self._VALID_BTNS:
            if retry_cnt < 2:
                self.logger.warning(
                    f"Invalid BTN '{raw}' → retry {retry_cnt+1}/3"
                )
                return {"tool_error": {
                    "name": "turn_player",
                    "reason": f"invalid_button:{raw}",
                    "retry_payload": json.dumps(
                        {"button": "A", "_retry": retry_cnt + 1}
                    )
                }}
            # after three failures—log and give up
            self.memory_mgr.update_context(
                f"[ERROR] turn_player failed 3× for '{raw}'."
            )
            return {"tool_error": {
                "name": "turn_player",
                "reason": "permanent_invalid"
            }}

        self.logger.info(f"(Tool) turn_player => pressing {button}")
        
        mapper.update()
        mapper.save_all_maps()
        mid, x, y, facing = mapper.get_player_pos()

        if facing == button:
            self.memory_mgr.update_context(f"[PERCEPTION] Player already facing {button}.")
            self.logger.info(f"(Tool) turn_player => Player already facing {button}.")
            return {"tool_error": {"name": "turn_player",
                                   "reason": "Player already facing that direction."}}
        
        try:
            ga, oa, flag, shots, req, raw_resp = \
                general_perception.analyze_images_and_reasoning(
                    emulator=self.emulator,
                    button=button,
                    main_agent_move_reasoning=internal_thoughts,
                    short_context=short_context
                )
        except Exception as e:
            self.memory_mgr.update_context(f"[ERROR] {e}")
            return {"tool_error": {"name": "turn_player",
                                   "reason": str(e)}}

        # persist perception summary
        self.memory_mgr.update_context(f"[PERCEPTION] {ga}")

        return {
            "prompt_dict": {"note": "See PerceptionAgent code"},
            "request_payload": req,
            "raw_response":  raw_resp,
            "general_analysis": ga,
            "overworld_analysis": oa,
            "game_state_flag": flag,
            "screenshots": shots
        }
    
    def _handle_player_interact(self, args, internal_thoughts: str, short_context: str, general_perception, mapper):
        # auto-normalise casing
        raw       = args.get("button", "A")
        retry_cnt = args.get("_retry", 0)
        button    = self._canonical_button(raw)

        if button not in self._VALID_BTNS:
            if retry_cnt < 2:
                self.logger.warning(
                    f"Invalid BTN '{raw}' → retry {retry_cnt+1}/3"
                )
                return {"tool_error": {
                    "name": "player_interact",
                    "reason": f"invalid_button:{raw}",
                    "retry_payload": json.dumps(
                        {"button": "A", "_retry": retry_cnt + 1}
                    )
                }}
            # after three failures—log and give up
            self.memory_mgr.update_context(
                f"[ERROR] player_interact failed 3× for '{raw}'."
            )
            return {"tool_error": {
                "name": "player_interact",
                "reason": "permanent_invalid"
            }}

        self.logger.info(f"(Tool) player_interact => pressing {button}")
        
        try:
            ga, oa, flag, shots, req, raw_resp = \
                general_perception.analyze_images_and_reasoning(
                    emulator=self.emulator,
                    button=button,
                    main_agent_move_reasoning=internal_thoughts,
                    short_context=short_context
                )
        except Exception as e:
            self.memory_mgr.update_context(f"[ERROR] {e}")
            return {"tool_error": {"name": "player_interact",
                                   "reason": str(e)}}

        # persist perception summary
        self.memory_mgr.update_context(f"[PERCEPTION] {ga}")

        return {
            "prompt_dict": {"note": "See PerceptionAgent code"},
            "request_payload": req,
            "raw_response":  raw_resp,
            "general_analysis": ga,
            "overworld_analysis": oa,
            "game_state_flag": flag,
            "screenshots": shots
        }