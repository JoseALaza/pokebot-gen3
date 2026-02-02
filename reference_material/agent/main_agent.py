# ──────────────────────────────────────────────────────────────────────────────
#  src/agent/main_agent.py   –  v2  (prompts delegated to src/prompts.py)
# ──────────────────────────────────────────────────────────────────────────────
import io
import json
import logging
import os
from pathlib import Path
import time
from typing import Dict, List

from PIL import Image

from src.agent.prompts import build_thinking_prompt, build_action_prompt
from src.agent.memory.memory_manager import MemoryManager
from src.agent.model_manager import ModelManager
from src.agent.toolset import Toolset
from src.vision.resnet_vision_tool import ResNetVisionTool
from src.agent.overworld.overworld_mapper import OverworldMapper
from src.agent.overworld.overworld_navigator import OverworldNavigator


class MainAgent:
    """
    Orchestrates thinking → action cycles.
    """

    # ──────────────────────────────────────────────────────────
    #  INITIALISATION
    # ──────────────────────────────────────────────────────────
    def __init__(
        self,
        emulator,
        memory_mgr: MemoryManager,
        model_mgr: ModelManager,
        general_perception,
        toolset: Toolset,
    ):
        self.emulator = emulator
        self.memory_mgr = memory_mgr
        self.model_mgr = model_mgr
        self.general_perception = general_perception
        self.toolset = toolset

        self.logger = logging.getLogger(__name__)
        self.current_mode = "general"

        # vision / mapping helpers
        MODEL_PATH = "ultra/runs/resnet/train_2/best_resnet.pth"
        vision_tool = ResNetVisionTool(MODEL_PATH)
        self.mapper = OverworldMapper(self.emulator, vision_tool=vision_tool)
        self.navigator = OverworldNavigator(
            self.emulator, self.mapper, self.general_perception, self.memory_mgr
        )

        self.iteration_count = self._detect_last_iteration()
        self.logger.info("Resuming at iteration #%d", self.iteration_count + 1)
        os.makedirs("src/logs/iterations", exist_ok=True)
        
    # ──────────────────────────────────────────────────────────
    #  HELPERS
    # ──────────────────────────────────────────────────────────
    def _get_textual_state(self) -> str:
        """
        Produce the textual scene snapshot that is used to feed the prompts.
        """
        move_direction = {
            "UP": (0, -1),
            "DOWN": (0, 1),
            "LEFT": (-1, 0),
            "RIGHT": (1, 0)
        }
        
        if (
            self.current_mode.upper() == "OVERWORLD"
            and self.emulator.get_current_game_state() == "OVERWORLD"
        ):
            self.mapper.update()
            _mid, x, y, facing = self.mapper.get_player_pos()
            return (
                "(MAP DATA IS X-Y COORDINATE BASED WITH (0,0) AS THE TOP LEFT CORNER)\n"
                "(TILE_MAP IS THE PRIMARY DATA SOURCE, IT IS A CSV OF ALL THE TILES IN THE MAP)\n"
                "(TRAVERSAL_MAP IS A CSV OF THE TRAVERSABLE TILES IN THE MAP, IT IS A SUBSET OF TILE_MAP AND GIVES TILES A TRAVERSABLE VALUE)\n"
                "(TRAVERSAL_MAP CONSISTS OF ?, Y, N, T. ? IS UNKNOWN MEANING IT COULD BE ANY TILE BUT SHOULD BE EXPLORED. Y IS TRAVERSABLE. N IS A SOLID NON-TRAVERSABLE TILE. T IS A TRANSITION TILE MEANING A NEW MAP/AREA IS FOUND)\n"
                "(DIRECT_TILE IS THE X-Y COORDINATES OF THE TILE THE PLAYER IS CURRENTLY FACING)\n"
                "(PRIORITY/IMPORTANCE OF DATA IS: tile_map > screenshot > traversal_map)\n"
                "tile_map:\n"
                + self.mapper.convert_tile_map()
                + "\n\n"
                + "traversal_map:\n"
                + self.mapper.convert_trav_map()
                + "\n\n"
                + f"Player Data (X, Y, Facing Direction): ({x}, {y}, {facing}, ({self.emulator.get_player_xy()[0] + move_direction[self.emulator.get_player_direction().upper()][0]},{self.emulator.get_player_xy()[1] + move_direction[self.emulator.get_player_direction().upper()][1]}) )"
            )
        return "General mode: Standard environment snapshot."
    
    def _detect_last_iteration(self) -> int:
        """
        Scan src/logs/iterations for files named iteration_###.json and
        return that highest number; returns 0 if none exist.

        If files are sparse (e.g. 001, 002, 005) we still resume at 5.
        """
        it_dir = Path("src/logs/iterations")
        if not it_dir.exists():
            return 0

        max_id = 0
        for f in it_dir.glob("iteration_*.json"):
            try:
                num_part = f.stem.split("_")[1]           # e.g. '007'
                idx = int(num_part.lstrip("0") or "0")    # '' ⇒ 0
                max_id = max(max_id, idx)
            except Exception:
                continue
        return max_id

    # ──────────────────────────────────────────────────────────
    #  RUN LOOP
    # ──────────────────────────────────────────────────────────
    def run_loop(self) -> None:
        """
        Continuous perception → think → act loop.
        """

        # ------- First-time perception bootstrap ------------------------------
        (
            ga,
            _oa,
            flag,
            _shots,
            _perc_req,
            _perc_raw,
        ) = self.general_perception.analyze_images_and_reasoning(
            emulator=self.emulator,
            button="A",
            main_agent_move_reasoning="Agent starting, initial perception.",
            short_context="Initial bootstrap of perception.",
        )
        self.current_mode = flag.upper()
        self.memory_mgr.update_context(f"[PERCEPTION] {ga}")

        # ----------------------------------------------------------------------
        while True:
            self.iteration_count += 1
            iter_start = time.time()

            short_ctx = self.memory_mgr.get_short_term_context()
            mid_ctx = self.memory_mgr.get_medium_term_context()
            goals_txt = self.memory_mgr.get_goals()
            text_state = self._get_textual_state()

            recent_thoughts_list = self.memory_mgr.get_internal_thoughts(last_n=30)
            recent_thoughts = "\n".join(recent_thoughts_list)
            recent_actions  = self.memory_mgr.get_action_history(30)
            

            # ---------------- THINKING PHASE ----------------------------------
            think_prompt_data = build_thinking_prompt(
                self.current_mode,
                self.emulator,
                text_state,
                short_ctx,
                mid_ctx,
                goals_txt,
                self.memory_mgr.data.get("knowledge_base", {}),
                recent_thoughts,
                recent_actions
                
            )

            internal_thoughts, think_req, think_raw = self.model_mgr.call_thinking_phase(
                think_prompt_data
            )
            tagged_thoughts = f"[ITERATION: {self.iteration_count} PLANS + ACTIONS] {internal_thoughts}"
            self.memory_mgr.add_internal_thoughts(tagged_thoughts)
            internal_thoughts = tagged_thoughts

            # ---------------- ACTION PHASE ------------------------------------
            act_prompt = build_action_prompt(
                self.current_mode,
                text_state,
                short_ctx,
                mid_ctx,
                goals_txt,
                internal_thoughts,
                self.memory_mgr.data.get("knowledge_base", {}),
                recent_thoughts,
                recent_actions
            )
            
            # llm_intended_tool_calls is the list of calls from ModelManager
            llm_calls, act_req, act_raw = self.model_mgr.call_action_selector(
                act_prompt, self.toolset.get_tool_schemas(self.current_mode.upper())
            )

            executed_tool_details: List[Dict] = []
            final_perception_block = None
            current_tool_error = None

            if not llm_calls:
                self.logger.info("No tool calls received from LLM for this iteration.")
            else:
                self.logger.info(f"LLM intended {len(llm_calls)} tool call(s): {llm_calls}")

                INTERNAL_TOOLS = {"write_to_memory", "update_goal"}
                WORLD_TOOLS = {"press_gba_button", "overworld_navigator", "move_player", "turn_player", "player_interact"}

                internal_queue = [c for c in llm_calls if c["name"] in INTERNAL_TOOLS]
                world_queue = [c for c in llm_calls if c["name"] in WORLD_TOOLS] + [
                    c for c in llm_calls if c["name"] not in ( INTERNAL_TOOLS | WORLD_TOOLS)
                ]

                # ---- execute internal first ---------------------------------
                for call in internal_queue:
                    log_entry = {
                        "name": call["name"],
                        "arguments": call["arguments"],
                        "execution_priority": "internal",
                    }
                    self.logger.info(f"Executing internal tool: {call['name']}")
                    result = self.toolset.handle_single_function_call(
                        general_perception=self.general_perception,
                        tool_call_instruction=call,
                        internal_thoughts=internal_thoughts,
                        short_context=short_ctx,
                        mapper=self.mapper,
                        navigator=self.navigator,
                    )
                    if isinstance(result, dict) and "tool_error" in result:
                        current_tool_error = result["tool_error"]
                        log_entry.update(status="error", error_details=current_tool_error)
                        executed_tool_details.append(log_entry)
                        self.logger.error(
                            f"Error during internal tool {call['name']}: {current_tool_error}"
                        )
                        break
                    log_entry["status"] = "success"
                    executed_tool_details.append(log_entry)
                    log_entry["iteration"] = self.iteration_count

                # ---- execute first world tool (if no error) -----------------
                if not current_tool_error and world_queue:
                    for call in world_queue:
                        log_entry = {
                            "name": call["name"],
                            "arguments": call["arguments"],
                            "execution_priority": "world_interaction",
                        }
                        log_entry["iteration"] = self.iteration_count
                        
                        self.logger.info(f"Executing world tool: {call['name']}")
                        result = self.toolset.handle_single_function_call(
                            general_perception=self.general_perception,
                            tool_call_instruction=call,
                            internal_thoughts=internal_thoughts,
                            short_context=short_ctx,
                            mapper=self.mapper,
                            navigator=self.navigator,
                        )
                        if isinstance(result, dict) and "tool_error" in result:
                            current_tool_error = result["tool_error"]
                            log_entry.update(status="error", error_details=current_tool_error)
                        elif isinstance(result, dict) and "general_analysis" in result:
                            final_perception_block = result
                            # self.memory_mgr.update_context(f"[PERCEPTION] {final_perception_block['general_analysis']}")
                            log_entry["perception_block"] = final_perception_block
                            log_entry["status"] = "success_with_perception"
                        else:
                            log_entry["status"] = "warning_no_perception"
                        
                        executed_tool_details.append(log_entry)

                if executed_tool_details:
                    self.memory_mgr.add_action_history(executed_tool_details)


            # ------------------------------------------------------------------
            iter_end = time.time()

            # ------- build iteration JSON -------------------------------------
            def _safe_list(val):
                if val is None:
                    return []
                if isinstance(val, (list, tuple)):
                    return list(val)
                return [val]

            try:
                iter_data: Dict[str, any] = {
                    "iteration": self.iteration_count,
                    "iteration_start_time": time.strftime(
                        "%Y-%m-%d %H:%M:%S", time.localtime(iter_start)
                    ),
                    "iteration_end_time": time.strftime(
                        "%Y-%m-%d %H:%M:%S", time.localtime(iter_end)
                    ),
                    # thinking
                    "thinking_phase": {
                        "prompt_dict": think_prompt_data,
                        "request_payload": think_req,
                        "raw_response": think_raw,
                        "internal_thoughts": internal_thoughts,
                        "main_screenshot": think_prompt_data["main_screenshot"],
                    },
                    # action
                    "action_phase": {
                        "prompt_dict": act_prompt,
                        "request_payload": act_req,
                        "raw_response": act_raw,
                        "llm_intended_tool_calls": llm_calls,
                        "executed_tool_details": executed_tool_details,
                    },
                    # memory delta
                    "memory_updates": _safe_list(
                        getattr(self.memory_mgr, "last_summary", None)
                    ),
                }

                # ---- perception integration ---------------------------------
                if final_perception_block:
                    iter_data["perception_phase"] = final_perception_block

                    try:
                        block = final_perception_block
                        gsf = None
                        if isinstance(block, dict):
                            gsf = block.get("game_state_flag")
                            if not gsf:
                                gsf = next(
                                    (
                                        v.get("game_state_flag")
                                        for v in block.values()
                                        if isinstance(v, dict)
                                        and v.get("game_state_flag") is not None
                                    ),
                                    None,
                                )

                        if gsf:
                            self.current_mode = gsf.upper()

                            # short-term context update
                            ga_txt = block.get("general_analysis")
                            if not ga_txt:
                                ga_txt = next(
                                    (
                                        v.get("general_analysis")
                                        for v in block.values()
                                        if isinstance(v, dict)
                                        and v.get("general_analysis")
                                    ),
                                    None,
                                )
                            if ga_txt:
                                # self.memory_mgr.update_context(f"[PERCEPTION] {ga_txt}")
                                self.logger.info("Perception update here")
                        else:
                            self.logger.warning(
                                "Could not determine game_state_flag from perception block."
                            )
                    except Exception as e:
                        self.logger.error(
                            f"Error parsing perception block: {e} | block={json.dumps(block)[:500]}"
                        )

                # ---- full memory snapshot -----------------------------------
                iter_data["all_memory"] = {
                    "short_term_context": _safe_list(
                        self.memory_mgr.get_short_term_context(last_n=15)
                    ),
                    "medium_term_context": _safe_list(
                        self.memory_mgr.get_medium_term_context()
                    ),
                    "knowledge_base": dict(
                        self.memory_mgr.data.get("knowledge_base", {})
                    ),
                    "goals": _safe_list(
                        self.memory_mgr.data.get("goals", [])
                        ),
                    "recent_internal_thoughts": self.memory_mgr.get_internal_thoughts()
                }

                # reset summary flag
                self.memory_mgr.last_summary = None

                # ---- write file ---------------------------------------------
                log_path = os.path.join(
                    "src", "logs", "iterations", f"iteration_{self.iteration_count:03}.json"
                )
                with open(log_path, "w", encoding="utf-8") as fp:
                    json.dump(iter_data, fp, indent=2)

            except Exception as err:
                self.logger.error(f"[ITER LOG] failed to build/write: {err}")
            try:
                save_dir = (Path(__file__).parent.parent / "logs" / "saveStates").resolve()
                save_dir.mkdir(parents=True, exist_ok=True)

                save_path = save_dir / f"agent_auto.State"
                self.emulator.save_state(str(save_path))
                self.logger.info("Saved state → %s", save_path)   # full absolute path
            except Exception as e:
                self.logger.error("Auto-save failed: %s", e)

            iter_time= iter_end - iter_start
            if iter_time < 30:
                self.logger.info("Iteration took %.2f seconds, waiting for 30 seconds before next iteration.", iter_time)
                time.sleep(30 - iter_time)
            print("iteration %d took %.2f seconds" % (self.iteration_count, iter_time))
