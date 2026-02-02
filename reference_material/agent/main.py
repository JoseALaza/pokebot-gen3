import logging
import sys
import os
from dotenv import load_dotenv
from pathlib import Path

from src.core.emulator import BizHawkEmulator

# Memory, Goals, Model, Perception, Agent
from src.agent.memory.memory_manager import MemoryManager
from src.agent.model_manager import ModelManager
from src.agent.perception.perception_agent import PerceptionAgent
from src.agent.toolset import Toolset
from src.agent.main_agent import MainAgent

def main():
    logging.basicConfig(level=logging.DEBUG)
    logging.getLogger('PIL').setLevel(logging.WARNING)
    load_dotenv()

    # 1) Load environment paths
    bizhawk_path = os.getenv("BIZHAWK_PATH")
    rom_path = os.getenv("ROM_PATH")
    lua_path = os.getenv("LUA_PATH")

    if not all([bizhawk_path, rom_path, lua_path]):
        sys.exit("Must define BIZHAWK_PATH, ROM_PATH, LUA_PATH in .env")

    repo_root      = Path(__file__).resolve().parents[2]   
    print("Repo root:", repo_root)     
    save_state_rel = Path("src/logs/saveStates/agent_auto.State")   
    save_state_abs = (repo_root / save_state_rel).resolve()

    resume_state = str(save_state_abs) if save_state_abs.exists() else None
    print("Resume state:", resume_state or "clean start")
    logging.info("Resuming from %s", resume_state or "clean start")

    # 2) Create and start BizHawkEmulator
    emulator = BizHawkEmulator(
        bizhawk_path=bizhawk_path,
        rom_path=rom_path,
        lua_path=lua_path,
        save_state=resume_state
        )

    # 3) Build memory & goals
    memory_mgr = MemoryManager(file_path="src/agent/agent_memory/context/agent_memory.json")

    # 4) Create the model manager
    model_mgr = ModelManager()  # Reads OPENAI_API_KEY, etc.

    # 5) Instantiate the unified perception agent (serves both general and overworld roles)
    perception_agent = PerceptionAgent()

    # 6) Build the toolset (function calling definitions + handle code)
    toolset = Toolset(
        emulator=emulator,
        memory_mgr=memory_mgr,
    )

    # 7) Create the main hierarchical agent,
    # passing the unified perception agent as the general perception module.
    agent = MainAgent(
        emulator=emulator,
        memory_mgr=memory_mgr,
        model_mgr=model_mgr,
        general_perception=perception_agent,
        toolset=toolset
    )

    # 8) Run the main agent loop
    try:
        agent.run_loop()
    except KeyboardInterrupt:
        print("Exiting via Ctrl+C.")
    except Exception as e:
        logging.exception("Agent encountered an error: %s", e)
    finally:
        emulator.close()
        print("Emulator closed. Exiting.")

if __name__ == "__main__":
    main()
