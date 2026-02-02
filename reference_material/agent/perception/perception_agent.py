# src/agent/perception/perception_agent.py

import os
import time
import glob
import base64
import json
from typing import Tuple, List, Dict
from pydantic import BaseModel
from PIL import Image

from google import genai
from google.genai import types

class PerceptionAgentOutput(BaseModel):
    general_analysis: str
    overworld_analysis: str
    game_state_flag: str

class PerceptionAgent:
    def __init__(self, gemini_api_key: str = None):
        if gemini_api_key is None:
            gemini_api_key = os.getenv("GEMINI_API_KEY", "MISSING_API_KEY")
        self.client = genai.Client(api_key=gemini_api_key)

    def analyze_images_and_reasoning(
        self,
        emulator,
        button: str,
        main_agent_move_reasoning: str,
        short_context: str
    ) -> Tuple[
        str,                 # general_analysis
        str,                 # overworld_analysis
        str,                 # game_state_flag
        List[Dict[str, str]],# screenshot_data
        Dict,                # request_payload
        str                  # raw_response as JSON string
    ]:
        move_direction = {
            "UP": (0, -1),
            "DOWN": (0, 1),
            "LEFT": (-1, 0),
            "RIGHT": (1, 0),
            "UNKNOWN": (0, 0)
        }
        # 1) Capture screenshot BEFORE the move
        screenshot_paths = []
        try:
            pre_move_ss = emulator.get_screenshot_perception()
            screenshot_paths.append(pre_move_ss)
        except Exception as e:
            raise RuntimeError(f"Failed to capture pre-move screenshot: {e}")
        
        # 2) Get player information before the move
        if emulator.get_player_xy() and emulator.get_player_direction():
            player_x, player_y = emulator.get_player_xy()
            player_facing = emulator.get_player_direction()
            facing_tile_x = player_x + move_direction[player_facing.upper()][0]
            facing_tile_y = player_y + move_direction[player_facing.upper()][1]
        else:
            player_x = "NA"
            player_y = "NA"
            player_facing = "NA"
            facing_tile_x = "NA"
            facing_tile_y = "NA"
        

        # 3) Press the button
        try:
            emulator.press_button(button)
        except Exception as e:
            raise RuntimeError(f"Failed to press button {button}: {e}")

        # 4) Capture 7 post-move screenshots, each after 0.5s
        for i in range(6):
            try:
                post_move_ss = emulator.get_screenshot_perception()
                screenshot_paths.append(post_move_ss)
            except Exception as e:
                raise RuntimeError(f"Failed to capture post-move screenshot {i+1}: {e}")
            time.sleep(0.4)

        time.sleep(1)
        try:
            pre_move_ss = emulator.get_screenshot_perception()
            screenshot_paths.append(pre_move_ss)
        except Exception as e:
            raise RuntimeError(f"Failed to capture pre-move screenshot: {e}")
        
        # 5) Get player information after the move
        if emulator.get_player_xy() and emulator.get_player_direction():
            after_player_x, after_player_y = emulator.get_player_xy()
            after_player_facing = emulator.get_player_direction()
            after_facing_tile_x = after_player_x + move_direction[after_player_facing.upper()][0]
            after_facing_tile_y = after_player_y + move_direction[after_player_facing.upper()][1]
        else:
            player_x = "NA"
            player_y = "NA"
            player_facing = "NA"
            facing_tile_x = "NA"
            facing_tile_y = "NA"

        # 5) Build system and user prompts (DO NOT CHANGE PROMPTS)
        system_msg = (
            "You are the PERCEPTION SUBAGENT for a Pokémon FireRed PLAYER AGENT. "
            "We provide you a list of 8 game screenshots, the first one is taken BEFORE the player's move, the next 6 are taken AFTER the player's move 0.4s apart, and the last one is taken 0.8s after the 7th screenshot and should be used to verify and double check what has happened between all the screenshots."
            "We also provide you with player information such as X position, Y position, and the direction the player is facing and the coordinates of the tile the player is facing. This should be taken into account and mentioned in your analysis,\n"
            "You are given:\n"
            "1) The move the agent decided on (and the reasoning)\n"
            "2) A short chunk of prior context from memory\n"
            "3) The 8 screenshots.\n"
            "4) Player information before the move: X position, Y position, Direction player is facing, Coordinates of the tile the player is facing.\n"
            "5) Player information after the move: X position, Y position, Direction player is facing, Coordinates of the tile the player is facing.\n\n"
            "YOUR TASK:\n"
            "Produce a final answer with EXACTLY three bracketed sections:\n"
            "  [general analysis]: (3-4 sentences describing key events or dialogue in these images and outcomes of the move taken. Also pass the Player information that was used in the analysis)\n"
            "  [overworld analysis]: (2-3 sentences describing if we're in overworld, and whether the player has free movement)\n"
            "  [game_state_flag]: (One word; 'overworld', 'battle', 'menu', 'dialogue', 'cutscene')\n\n"
            "IMPORTANT:\n"
            " - DO NOT omit or rename these bracket labels.\n"
            " - Provide concise but thorough analysis.\n"
            " - if you see a menu, describe it in general analysis.\n"
            " - Only set game_state_flag:overworld if any other options do not apply.\n"
        )

        user_msg = (
            f"Last action performed: {button}\n\n"
            f"Main agent's final thoughts:\n{main_agent_move_reasoning}\n\n"
            "Recent short-term memory:\n"
            f"{short_context}\n\n"
            "Now we show 8 screenshots total.\n"
            "Screenshot 1 => BEFORE the move.\n"
            "Screenshots 2..7 => AFTER the move, each ~0.4s apart.\n"
            "Screenshot 8 => 0.8s after the last screenshot.\n"
            "After the images, you will see (END_OF_SERIES). "
            f"Player information before the move: ({player_x}, {player_y}, {player_facing}, ({facing_tile_x}, {facing_tile_y}))"
            f"Player information after the move: ({after_player_x}, {after_player_y}, {after_player_facing}, ({after_facing_tile_x}, {after_facing_tile_y}))\n\n"
            "Then produce the bracketed output.\n"
        )

        schema_prompt = (
            "Use this JSON schema:\n\n"
            "PerceptionAgentOutput = {\n"
            "  'general_analysis': str,\n"
            "  'overworld_analysis': str,\n"
            "  'game_state_flag': str\n"
            "}\n\n"
            "Return: PerceptionAgentOutput"
        )

        final_marker = "(END_OF_SERIES)"

        # 6) Convert each screenshot path into a PIL image for the API call
        image_parts = []
        for path in screenshot_paths:
            try:
                pil_image = Image.open(path).convert("RGB")
                image_parts.append(pil_image)
            except Exception as e:
                raise RuntimeError(f"Failed to open screenshot image from {path}: {e}")

        # 7) Construct the complete contents for the Gemini API call.
        complete_contents = [
            {"text": system_msg},
            {"text": user_msg + "\n\n" + schema_prompt},
        ]
        for img in image_parts:
            complete_contents.append(img)
        complete_contents.append({"text": final_marker})

        # 8) Prepare configuration and request payload details for logging
        request_payload = {
            "model": "gemini-2.0-flash",
            "temperature": 1.0,
            "max_output_tokens": 2048,
            "response_mime_type": "application/json",
            "response_schema": "PerceptionAgentOutput",
            "note": "Conversation messages in 'complete_contents'"
        }

        config = types.GenerateContentConfig(
            temperature=1.0,
            max_output_tokens=2048,
            response_mime_type="application/json",
            response_schema=PerceptionAgentOutput,
        )

        # 9) Call Gemini API
        chat = self.client.chats.create(model="gemini-2.0-flash")
        final_response = chat.send_message(complete_contents, config=config)
        if not final_response.parsed:
            raise ValueError("Gemini did not return valid structured JSON.")

        output_obj = final_response.parsed  # Expected to be a PerceptionAgentOutput instance
        if not isinstance(output_obj, PerceptionAgentOutput):
            raise ValueError("Parsed object is not of type PerceptionAgentOutput.")

        # 10) Instead of using MessageToDict (which expects a protobuf), we use the pydantic .dict() method.
        raw_resp_text = json.dumps(final_response.dict(), indent=2)

        # 11) Base64-encode the screenshots for later display in the frontend.
        screenshot_data = []
        for path in screenshot_paths:
            try:
                with open(path, "rb") as f:
                    raw_bytes = f.read()
                    b64_str = base64.b64encode(raw_bytes).decode("utf-8")
                screenshot_data.append({
                    "filename": path,
                    "base64_data": b64_str
                })
            except Exception as e:
                print(f"Warning: Could not base64-encode {path}: {e}")

        

        # 12) Clear the perception screenshots directory
        perception_dir = os.path.join("src", "core", "screenshots", "perception")
        for file_path in glob.glob(os.path.join(perception_dir, "*")):
            try:
                os.remove(file_path)
            except Exception:
                pass

        # 13) Return all necessary data
        return (
            output_obj.general_analysis,
            output_obj.overworld_analysis,
            output_obj.game_state_flag,
            screenshot_data,
            request_payload,
            raw_resp_text
        )
