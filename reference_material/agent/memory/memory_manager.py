import json, logging, os, time, requests
from typing import List

class MemoryManager:
    """
    Unified memory layer:
      • short_term_context (list[str])
      • medium_term_context (list[str])
      • knowledge_base  (dict[str,str])
      • goals           (list[str])
      • summaries_history (debug)
      • internal_thoughts_window  (thinking-phase monologue)
      • action_history    (action-phase steps taken per iteration)

    All keys live in agent_memory.json, so a restart restores *everything*.
    """

    DEFAULT_MODEL = "gpt-4o-mini-2024-07-18"

    def __init__(self, file_path="src/agent/agent_memory/context/agent_memory.json"):
        self.log       = logging.getLogger(__name__)
        self.file_path = file_path
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)

        self.openai_api_key = os.getenv("OPENAI_API_KEY") or self._die("OPENAI_API_KEY")
        self.base_url       = "https://api.openai.com/v1/chat/completions"

        # ---------- default skeleton ----------
        self.data = {
            "short_term_context": [],
            "medium_term_context": [],
            "knowledge_base": {},
            "goals": [],
            "summaries_history": [],
            "internal_thoughts_window": [],
            "action_history": []
        }
        self.last_summary = None
        self._load()

    # ── CRUD helpers ─────────────────────────────────────────────
    def _load(self):
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    disk = json.load(f)
                # make sure every key exists
                for k in self.data:
                    if k not in disk:
                        disk[k] = self.data[k]
                self.data = disk
                self.log.info("[Memory] loaded %s", self.file_path)
            except Exception as e:
                self.log.warning("[Memory] failed to load (%s) – fresh start", e)

    def _save(self):
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            self.log.error("[Memory] save-error: %s", e)

    def _die(self, var):  # env helper
        raise ValueError(f"Missing {var} in environment")

    # ── Context API (unchanged) ───────────────────────────────────
    def get_short_term_context(self, last_n=5) -> str:
        return "\n".join(self.data["short_term_context"][-last_n:])

    def get_medium_term_context(self) -> str:
        return "\n".join(self.data["medium_term_context"])

    def update_context(self, new_info: str):
        self.data["short_term_context"].append(new_info)
        self.last_summary = None

        if len(self.data["short_term_context"]) >= 15:
            oldest = self.data["short_term_context"][:10]
            summary = self._summarize_entries(oldest)
            self.data["short_term_context"] = self.data["short_term_context"][10:]
            self.data["medium_term_context"].append(summary)
            self.data["summaries_history"].append({
                "ts": time.time(),
                "src": oldest,
                "summary": summary
            })
            self.last_summary = summary

        self._save()
        return self.last_summary

    # (same _summarize_entries helper as before …)

    # ── Knowledge-base helpers ───────────────────────────────────
    def read_kb(self, key):         return self.data["knowledge_base"].get(key)

    def write_kb(self, key, value):
        self.data["knowledge_base"][key] = value
        self._save()

    # ── GOALS API ────────────────────────────────────────────────
    def get_goals(self) -> str:
        return "\n".join(f"- {g}" for g in self.data["goals"])
    
    def goals(self) -> list[str]:
        return self.data["goals"]

    def add_goal(self, goal: str):
        if goal not in self.data["goals"]:
            self.data["goals"].append(goal)
            self._save();  self.log.info("[Goals] + %s", goal)

    def remove_goal(self, goal: str):
        if goal in self.data["goals"]:
            self.data["goals"].remove(goal)
            self._save();  self.log.info("[Goals] – %s", goal)

    def _create_response(self, payload: dict) -> dict:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.openai_api_key}"
        }
        self.log.debug("Sending summarization payload:\n" + json.dumps(payload, indent=2))
        try:
            response = requests.post(self.base_url, headers=headers, json=payload)
            self.log.debug(f"HTTP Status Code: {response.status_code}")
            self.log.debug("Raw Summarization Response:\n" + response.text)
            response.raise_for_status()
            response_json = response.json()
            self.log.debug("Parsed Summarization JSON:\n" + json.dumps(response_json, indent=2))
            return response_json
        except Exception as e:
            self.log.error(f"Error calling Chat Completions endpoint: {e}")
            raise

    def _summarize_entries(self, entries: list) -> str:
        """
        Summarize the 10 lines in 2-3 concise sentences.
        """
        prompt = (
            "Summarize the following 10 lines of context in 2-3 concise sentences:\n\n" +
            "\n".join(entries)
        )
        messages = [
            {"role": "system", "content": "You are a concise summarizer."},
            {"role": "user", "content": prompt}
        ]
        payload = {
            "model": self.DEFAULT_MODEL,
            "messages": messages,
            "temperature": 0.5,
            "max_tokens": 150
        }

        try:
            response_json = self._create_response(payload)
            choices = response_json.get("choices", [])
            if not choices:
                return "Summary unavailable (no choices)."
            message = choices[0].get("message", {})
            summary = message.get("content", "").strip()
            return summary if summary else "Summary unavailable (empty)."
        except Exception as e:
            self.log.error(f"Error summarizing context entries: {e}")
            return "Summary unavailable (exception)."
        

    # ── Rolling internal-thoughts window ─────────────────────────────
    def add_internal_thoughts(self, thoughts: str, window_size: int | None = None):
        """
        Append one complete `internal_thoughts` string and keep only the
        most-recent N (default 10, or override with env THOUGHT_WINDOW
        or with the `window_size` argument).
        """
        if thoughts is None:
            return

        if window_size is None:
            window_size = int(os.getenv("THOUGHT_WINDOW", 30))

        buf = self.data["internal_thoughts_window"]
        buf.append(thoughts.strip())

        if len(buf) > window_size:
            self.data["internal_thoughts_window"] = buf[-window_size:]

        self._save()

    def get_internal_thoughts(self, last_n: int | None = None) -> list[str]:
        """
        Return the most-recent thoughts (newest last).  If `last_n` is None,
        the entire buffer is returned.
        """
        buf = self.data.get("internal_thoughts_window", [])
        return buf if last_n is None else buf[-last_n:]
    

    # ─── NEW: action history API ────────────────────────────────────────────
    def add_action_history(self, actions: List[dict], window_size: int | None = None):
        """
        Append a list describing all tool-calls of one iteration.
        Each item should already be JSON-serialisable.
        """
        if not actions: return
        if window_size is None:
            window_size = int(os.getenv("ACTION_WINDOW", 30))
        buf = self.data["action_history"]
        buf.append(actions)
        if len(buf) > window_size:
            self.data["action_history"] = buf[-window_size:]
        self._save()

    def get_action_history(self, last_n: int | None = None) -> List[List[dict]]:
        buf = self.data.get("action_history", [])
        return buf if last_n is None else buf[-last_n:]
