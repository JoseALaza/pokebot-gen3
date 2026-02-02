# src/agent/memory/goals_manager.py

import logging

class GoalsManager:
    """
    Stores a list of goals. 
    You can store them in memory or a separate file if desired.
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        # For now, we just keep them in memory
        # Optionally load from disk, or from MemoryManager
        self.goals = [
        ]

    def get_goals(self):
        return "\n".join(f"- {g}" for g in self.goals)

    def add_goal(self, goal: str):
        if goal not in self.goals:
            self.goals.append(goal)
            self.logger.info(f"[GoalsManager] Added goal: {goal}")

    def remove_goal(self, goal: str):
        if goal in self.goals:
            self.goals.remove(goal)
            self.logger.info(f"[GoalsManager] Removed goal: {goal}")
