# overworld_navigator.py

import time
import logging
from queue import PriorityQueue
from src.agent.overworld.map_enums import MapFRLG

logger = logging.getLogger(__name__)

def _normalize_map_tuple(map_tuple):
    """
    If (group, number) is recognized in MapFRLG, return that enum member.
    Otherwise, return the raw (group, number).
    """
    try:
        return MapFRLG(map_tuple)
    except ValueError:
        return map_tuple

class OverworldNavigator:
    """
    Very minimal navigator that just does:
      1) Press a button
      2) Wait
    We'll rely on OverworldMapper to do the actual mapping.
    """

    def __init__(self, emulator, mapper, general_perception, memory_mgr):
        self.emulator = emulator
        self.mapper = mapper
        self.general_perception = general_perception
        self.memory_mgr = memory_mgr

    def get_turns(self, current_direction, required_direction):
        """
        Determines the necessary turn inputs to change from current_direction
        to required_direction.
        """
        turns = []
        if current_direction == "Up":
            if required_direction == "Left":
                turns.insert(0,"Left")
            elif required_direction == "Right":
                turns.insert(0,"Right")
            elif required_direction == "Down":
                turns.insert(0,"Down")
        elif current_direction == "Down":
            if required_direction == "Right":
                turns.insert(0,"Right")
            elif required_direction == "Left":
                turns.insert(0,"Left")
            elif required_direction == "Up":
                turns.insert(0,"Up")
        elif current_direction == "Left":
            if required_direction == "Up":
                turns.insert(0,"Up")
            elif required_direction == "Down":
                turns.insert(0,"Down")
            elif required_direction == "Right":
                turns.insert(0,"Right")
        elif current_direction == "Right":
            if required_direction == "Down":
                turns.insert(0,"Down")
            elif required_direction == "Up":
                turns.insert(0,"Up")
            elif required_direction == "Left":
                turns.insert(0,"Left")
        return turns

    def return_directions(self, target_x: int, target_y: int):
        """
        Returns a list of directions (including turns) needed to reach the target coordinate.
        Does not execute any moves, just plans the path and converts it to directions.
        Returns: List of directions or None if no path is found
        """
        movements = {
            "Up": (0, -1),
            "Down": (0, 1),
            "Left": (-1, 0),
            "Right": (1, 0),
        }
        
        map_tuple = self.emulator.get_map_id()
        current_map_id = _normalize_map_tuple(map_tuple)
        traversal_map = self.mapper.scenes.get(current_map_id)

        current_dir = self.emulator.get_player_direction()

        def heuristic(x1, y1, x2, y2):
            return abs(x1 - x2) + abs(y1 - y2)

        def is_goal_reachable(goal_x, goal_y):
            """Check if the goal is reachable (either walkable or has an adjacent walkable tile)"""
            goal_tile = traversal_map.trav_map.get(goal_y, goal_x)
            logger.warning(f"Goal tile: {goal_tile}")
            
            # If the goal is non-walkable (N), check adjacent tiles
            adjacent_walkable = False
            for _, (dx, dy) in movements.items():
                adj_x, adj_y = goal_x + dx, goal_y + dy
                adj_tile = traversal_map.trav_map.get(adj_y, adj_x)
                if adj_tile in ["Y", "?", "T"]:
                    adjacent_walkable = True
                    break
                
            return adjacent_walkable

        # Check if goal is reachable before starting pathfinding
        if not is_goal_reachable(target_x, target_y):
            logger.warning(f"Goal ({target_x}, {target_y}) is not reachable - no adjacent walkable tiles!")
            return f"Goal ({target_x}, {target_y}) is not reachable - no adjacent walkable tiles!"

        # Check if target is already marked as non-walkable
        target_tile = traversal_map.trav_map.get(target_y, target_x)
        if target_tile == "N":
            logger.warning(f"Target position ({target_x}, {target_y}) is marked as non-walkable!")
            return f"Target position ({target_x}, {target_y}) is marked as non-walkable!"

        current_x, current_y = self.mapper.get_player_pos()[1:3]

        # A* pathfinding
        start = (current_x, current_y)
        goal = (target_x, target_y)

        frontier = PriorityQueue()
        frontier.put((0, start))
        
        came_from = {start: None}
        cost_so_far = {start: 0}

        # Find path
        while not frontier.empty():
            current_priority, current = frontier.get()
            x, y = current

            if current == goal:
                break

            for direction, (dx, dy) in movements.items():
                next_x, next_y = x + dx, y + dy
                next_node = (next_x, next_y)

                # Check if the next position is walkable
                next_tile = traversal_map.trav_map.get(next_y, next_x)
                if next_tile is not None and next_tile != "N":
                    new_cost = cost_so_far[current] + 1
                    if next_tile == "?":
                        new_cost += 0.1

                    if next_node not in cost_so_far or new_cost < cost_so_far[next_node]:
                        cost_so_far[next_node] = new_cost
                        priority = new_cost + heuristic(next_x, next_y, target_x, target_y)
                        frontier.put((priority, next_node))
                        came_from[next_node] = current

        # If goal not found in came_from, no path exists
        if goal not in came_from:
            return None

        # Reconstruct path
        path = []
        current = goal
        while current != start:
            path.append(current)
            current = came_from[current]
        path.reverse()

        # Convert path to directions
        directions = []
        current_dir = self.emulator.get_player_direction()

        for i in range(len(path)):
            x0, y0 = start if i == 0 else path[i-1]
            x1, y1 = path[i]

            # Determine required direction
            if x1 > x0:
                required_direction = "Right"
            elif x1 < x0:
                required_direction = "Left"
            elif y1 > y0:
                required_direction = "Down"
            elif y1 < y0:
                required_direction = "Up"

            # Add any necessary turns
            if current_dir != required_direction:
                turns = self.get_turns(current_dir, required_direction)
                directions.extend(turns)
                current_dir = required_direction

            # Add the movement direction
            directions.append(required_direction)

        return directions

    def execute_moves(self, directions: list, internal_thoughts: str, short_context: str):
        """
        Executes a list of directions.
        
        Args:
            directions: List of directions (including turns)
            current_x, current_y: Starting position
            mapper: OverworldMapper instance for position updates
        
        Returns:
            tuple: (success: bool, reason: str, new_x: int, new_y: int)
                success: Whether the entire sequence completed successfully
                reason: Description of what happened
                new_x, new_y: Final position coordinates
        """
        
        movements = {
            "Up": (0, -1),
            "Down": (0, 1),
            "Left": (-1, 0),
            "Right": (1, 0),
        }

        (current_x, current_y) = self.mapper.get_player_pos()[1:3]

        #### PRE-EXECUTION CHECKS ####
        
        # Verify initial position for move execution as a precaution
        if self.mapper.get_player_pos()[1:3] != (current_x, current_y):
            logger.warning(f"Position mismatch! Expected ({current_x}, {current_y}), but got ({self.mapper.get_player_pos()[1:3]})")
            return False, "Position mismatch"
        
        perception_block = {
            "prompt_dict": {
                "note": "See PerceptionAgent code for details on exact messages"
            },
            "request_payload": "",
            "raw_response": "",
            "general_analysis": "",
            "overworld_analysis": "",
            "game_state_flag": "",
            "screenshots": "",
            "player_direction": "",
            "player_position_x": "",
            "player_position_y": "",
            "mapping_data": {
                "tile_map": str(self.mapper.scenes.get(self.mapper.get_player_pos()[0]).tile_map),
                "traversal_map": str(self.mapper.scenes.get(self.mapper.get_player_pos()[0]).trav_map)
            },
            "moves_to_execute": directions,
        }
        
        perception_blocks = {}
        
        #### EXECUTION LOOP ####

        for i, direction in enumerate(directions):
            logger.info(f"Executing move {i+1}/{len(directions)}: {direction}")
            logger.info(f"Current directions: {directions}")

            #### PRE-MOVE VARIABLES ####

            # Placeholder variables for comparison
            placeholder_x, placeholder_y = current_x, current_y
            placeholder_map_data, _, _, placeholder_facing = self.mapper.get_player_pos()
            target_tile = (current_x+movements[direction][0], current_y+movements[direction][1])
            
            # Variables for map data
            map_tuple = self.emulator.get_map_id()
            current_map_id = _normalize_map_tuple(map_tuple)
            traversal_map = self.mapper.scenes.get(current_map_id)

            # Execute the move
            (
              general_analysis,
              overworld_analysis,
              game_state_flag,
              new_screenshots,
              perception_req_payload,
              perception_raw_response
            ) = self.general_perception.analyze_images_and_reasoning(
              emulator=self.emulator,
              button=direction,
              main_agent_move_reasoning=internal_thoughts,
              short_context=short_context
            )

            # Update the mapper to refresh player position and state
            # May be changed to RAM reading functions but should work with mapper
            self.mapper.update()
            updated_map_data, updated_x, updated_y, updated_facing = self.mapper.get_player_pos()
            new_traversal_map = self.mapper.scenes.get(updated_map_data)

            #### POST-MOVE CHECKS ####

            # Did the tile change after the move, True if it did
            tile_change = (updated_x, updated_y) != (placeholder_x, placeholder_y)
            # Did the facing change after the move, True if it did
            facing_change = updated_facing != placeholder_facing
            # Did the map data change after the move, True if it did
            map_change = updated_map_data != placeholder_map_data
            # Did the game state change after the move, True if it did (No comparison needed since we should only execute in overworld)
            game_state_change = game_state_flag.upper() != "OVERWORLD"
        



            # Success Flag
            # If current X Y is different, then we change traversal tile to Y and we continue loop.
            if tile_change and not facing_change and not map_change and not game_state_change:
                # Log successful move
                logger.info(f"Move successful: {direction}")
                # Mark the tile as walkable
                traversal_map.trav_map.set(placeholder_y, placeholder_x, "Y")
                current_x, current_y = updated_x, updated_y
                self.mapper.save_all_maps()
                
                perception_block["request_payload"] = perception_req_payload
                perception_block["raw_response"] = perception_raw_response
                perception_block["general_analysis"] = general_analysis + f" The move from ({placeholder_x}, {placeholder_y}) to ({updated_x}, {updated_y}) was successful."
                perception_block["overworld_analysis"] = overworld_analysis
                perception_block["game_state_flag"] = game_state_flag
                perception_block["screenshots"] = new_screenshots
                perception_block["player_direction"] = updated_facing
                perception_block["player_position_x"] = updated_x
                perception_block["player_position_y"] = updated_y
                
                perception_blocks[f"{i} Move"] = perception_block
                
                # Update context with the perception output (general analysis only).
                self.memory_mgr.update_context(f"[PERCEPTION] {general_analysis} The move from ({placeholder_x}, {placeholder_y}) to ({updated_x}, {updated_y}) was successful.")
                continue

            # Turn Flag
            # If current X Y is the same, but player direction is different, then we continue loop
            elif not tile_change and facing_change and not map_change and not game_state_change:
                # Log turn
                logger.info(f"Facing {placeholder_facing}, turning: {direction}")
                current_x, current_y = updated_x, updated_y
                self.mapper.save_all_maps()
                
                perception_block["request_payload"] = perception_req_payload
                perception_block["raw_response"] = perception_raw_response
                perception_block["general_analysis"] = general_analysis + f" The player successfully turned from {placeholder_facing} to {direction}. Still remains at {current_x}, {current_y}."
                perception_block["overworld_analysis"] = overworld_analysis
                perception_block["game_state_flag"] = game_state_flag
                perception_block["screenshots"] = new_screenshots
                perception_block["player_direction"] = updated_facing
                perception_block["player_position_x"] = updated_x
                perception_block["player_position_y"] = updated_y
                
                perception_blocks[f"{i} Move"] = perception_block
                
                self.memory_mgr.update_context(f"[PERCEPTION] {general_analysis} The player successfully turned from {placeholder_facing} to {direction}. Still remains at {current_x}, {current_y}.")
                continue
            
            # Transition Flag
            # If the MAP ID and NUMBER are different from the starting MAP ID AND NUMBER, then we change traversal tile to T and we stop loop and log.
            elif map_change:
                # Log map transition
                logger.info(f"Map transition detected at ({target_tile[0]}, {target_tile[1]})")
                # Mark the prev tile as Y and the "transition" tile as T
                traversal_map.trav_map.set(target_tile[1], target_tile[0], "T")
                traversal_map.trav_map.set(placeholder_y, placeholder_x, "Y")
                # The player is now in a new map, we need to update the coordinate it came from using the opposite direction of the move it just made
                new_traversal_map.trav_map.set(updated_y+(movements[directions[i-1]][1]*-1), updated_x+(movements[directions[i-1]][0]*-1), "T")
                self.mapper.save_all_maps()
                
                perception_block["request_payload"] = perception_req_payload
                perception_block["raw_response"] = perception_raw_response
                perception_block["general_analysis"] = general_analysis + f" The move from ({placeholder_x}, {placeholder_y}) to ({updated_x}, {updated_y}) triggered a transition to a new map."
                perception_block["overworld_analysis"] = overworld_analysis
                perception_block["game_state_flag"] = game_state_flag
                perception_block["screenshots"] = new_screenshots
                perception_block["player_direction"] = updated_facing
                perception_block["player_position_x"] = updated_x
                perception_block["player_position_y"] = updated_y
                
                perception_blocks[f"{i} Move"] = perception_block
                
                self.memory_mgr.update_context(f"[PERCEPTION] {general_analysis} The move from ({placeholder_x}, {placeholder_y}) to ({updated_x}, {updated_y}) triggered a transition to a new map.")
                # return perception_blocks
                return {
                    "prompt_dict": {"note": "See PerceptionAgent code"},
                    "request_payload": perception_req_payload,
                    "raw_response":  perception_raw_response,
                    "general_analysis": general_analysis + f" The move from ({placeholder_x}, {placeholder_y}) to ({updated_x}, {updated_y}) triggered a transition to a new map.",
                    "overworld_analysis": overworld_analysis,
                    "game_state_flag": game_state_flag,
                    "screenshots": new_screenshots
                }
            
            # Collision Flag
            # Does current X Y match after move? If so then it is a collision.
            # If collision, then we change traversal tile to N and we stop loop and log.
            elif not tile_change and not facing_change and not map_change and not game_state_change:
                logger.warning(f"Collision detected at ({target_tile[0]}, {target_tile[1]})")
                # Mark the tile as non-walkable
                traversal_map.trav_map.set(target_tile[1],target_tile[0], "N")
                self.mapper.save_all_maps()
                
                perception_block["request_payload"] = perception_req_payload
                perception_block["raw_response"] = perception_raw_response
                perception_block["general_analysis"] = general_analysis + f" The move from ({placeholder_x}, {placeholder_y}) to ({updated_x}, {updated_y}) resulted in a collision."
                perception_block["overworld_analysis"] = overworld_analysis
                perception_block["game_state_flag"] = game_state_flag
                perception_block["screenshots"] = new_screenshots
                perception_block["player_direction"] = updated_facing
                perception_block["player_position_x"] = updated_x
                perception_block["player_position_y"] = updated_y
                
                perception_blocks[f"{i} Move"] = perception_block
                
                self.memory_mgr.update_context(f"[PERCEPTION] {general_analysis} The move from ({placeholder_x}, {placeholder_y}) to ({updated_x}, {updated_y}) resulted in a collision.")
                # return perception_blocks
                return {
                    "prompt_dict": {"note": "See PerceptionAgent code"},
                    "request_payload": perception_req_payload,
                    "raw_response":  perception_raw_response,
                    "general_analysis": general_analysis + f" The move from ({placeholder_x}, {placeholder_y}) to ({updated_x}, {updated_y}) resulted in a collision.",
                    "overworld_analysis": overworld_analysis,
                    "game_state_flag": game_state_flag,
                    "screenshots": new_screenshots
                }
            
            # Event Flag
            # Using perception agent flags. If the game_state_flag.upper() != "OVERWORLD" and current_game_state != "OVERWORLD" Then we are in an event ie dialoge, battle, etc.
            # We stop loop and log
            elif game_state_change:
                logger.info(f"Event detected at ({placeholder_x}, {placeholder_y})")
                self.mapper.save_all_maps()

                self.memory_mgr.update_context(f"[PERCEPTION] {general_analysis} The move from ({placeholder_x}, {placeholder_y}) to ({updated_x}, {updated_y}) triggered an event.")
                
                perception_block["request_payload"] = perception_req_payload
                perception_block["raw_response"] = perception_raw_response
                perception_block["general_analysis"] = general_analysis + f" The move from ({placeholder_x}, {placeholder_y}) to ({updated_x}, {updated_y}) triggered an event."
                perception_block["overworld_analysis"] = overworld_analysis
                perception_block["game_state_flag"] = game_state_flag
                perception_block["screenshots"] = new_screenshots
                perception_block["player_direction"] = updated_facing
                perception_block["player_position_x"] = updated_x
                perception_block["player_position_y"] = updated_y
                
                perception_blocks[f"{i} Move"] = perception_block
                
                # return perception_blocks
                return {
                    "prompt_dict": {"note": "See PerceptionAgent code"},
                    "request_payload": perception_req_payload,
                    "raw_response":  perception_raw_response,
                    "general_analysis": general_analysis + f" The move from ({placeholder_x}, {placeholder_y}) to ({updated_x}, {updated_y}) triggered an event.",
                    "overworld_analysis": overworld_analysis,
                    "game_state_flag": game_state_flag,
                    "screenshots": new_screenshots
                }
            
            # May not be needed but just in case we save whatever map changes were made
            self.mapper.save_all_maps()
        
        # self.memory_mgr.update_context(f"[PERCEPTION] {general_analysis} Navigation execution was successful.")
        # If we completed all moves successfully we return False to end loop running in main_agent
        # return perception_blocks
        return {
            "prompt_dict": {"note": "See PerceptionAgent code"},
            "request_payload": perception_req_payload,
            "raw_response":  perception_raw_response,
            "general_analysis": perception_block["general_analysis"],
            "overworld_analysis": overworld_analysis,
            "game_state_flag": game_state_flag,
            "screenshots": new_screenshots
        }
