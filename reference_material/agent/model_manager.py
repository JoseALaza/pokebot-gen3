import os, time, json, logging, requests
from dotenv import load_dotenv

class ModelManager:
    """
    Dual-model dispatcher:
        THINKING → gpt-4.1       (default 1 M ctx)
        ACTION   → gpt-4.1-mini  (cheap, still supports tools)

    Override via env:
        THINK_MODEL=gpt-4.1
        ACT_MODEL=gpt-4.1-mini
    """

    CHAT_URL = "https://api.openai.com/v1/chat/completions"

    def __init__(self):
        self.log      = logging.getLogger(__name__)
        self.api_key  = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY missing")
        load_dotenv(override=True)
        self.think_model = "o4-mini-2025-04-16"
        self.act_model   = os.getenv("ACT_MODEL",   "gpt-4o-mini")

        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type":  "application/json"
        })

    # thinking-phase (4.1)
    def call_thinking_phase(self, prompt_dict: dict):
        payload = {
            "model":       self.think_model,
            "messages":    prompt_dict["messages"],
            "max_completion_tokens":  4000,
        }
        raw = self._post(payload)
        text = raw["choices"][0]["message"]["content"].strip()
        return text, payload, raw

    # action-phase (4.1-mini)
    def call_action_selector(self, prompt_dict: dict, tools: list):
        messages = [
            {"role": "system", "content": prompt_dict["system"]},
            {"role": "user",   "content": prompt_dict["user"]}
        ]
        payload = {
            "model":        self.act_model,
            "messages":     messages,
            "tools":        tools,
            "tool_choice":  "auto",
            "temperature":  0.1,
            "max_tokens":   1000
        }
        raw = self._post(payload)

        calls = []
        for choice in raw["choices"]:
            msg = choice["message"]
            for tc in msg.get("tool_calls", []):
                if tc["type"] == "function":
                    calls.append({
                        "name": tc["function"]["name"],
                        "arguments": tc["function"]["arguments"],  # dict
                        "id": tc["id"]
                    })
        return calls, payload, raw

    # low-level HTTP with retries
    def _post(self, payload: dict, tries: int = 3):
        for n in range(tries):
            try:
                r = self.session.post(self.CHAT_URL,
                                    data=json.dumps(payload),
                                    timeout=30)
                if r.status_code != 200:
                    print("**** OPENAI RAW ERROR ****")
                    print(r.text)                 # ← inspect this
                    print("***********************")
                r.raise_for_status()
                return r.json()
            except Exception as e:
                if n == tries - 1:
                    self.log.error("LLM call failed: %s", e)
                    raise
                time.sleep(1.5 * (n + 1))
