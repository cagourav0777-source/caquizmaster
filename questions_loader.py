import json
import logging
import random
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

class QuestionsManager:
    def __init__(self, filepath: str | Path = "data/questions.json"):
        self.filepath = Path(filepath)
        self.questions: List[Dict[str, Any]] = []
        self.load_questions()

    def load_questions(self) -> bool:
        if not self.filepath.exists():
            logger.error(f"File missing: {self.filepath}")
            return False
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.questions = [
                q for q in data 
                if q.get("question") and isinstance(q.get("options"), list) and 2 <= len(q["options"]) <= 10
            ]
            logger.info(f"Loaded {len(self.questions)} questions.")
            return True
        except Exception as e:
            logger.error(f"Error loading questions: {e}")
            return False

    def select_question(self, served_ids: set[str], subject: Optional[str] = None) -> tuple[Optional[Dict[str, Any]], bool]:
        if not self.questions:
            return None, False
        pool = self.questions
        if subject:
            filtered = [q for q in self.questions if subject.lower() in q.get("subject", "").lower()]
            if filtered:
                pool = filtered
        unserved = [q for q in pool if q["id"] not in served_ids]
        if not unserved:
            return random.choice(pool), True
        return random.choice(unserved), False

    def get_stats(self) -> Dict[str, Any]:
        counts: Dict[str, int] = {}
        for q in self.questions:
            s = q.get("subject", "Economics")
            counts[s] = counts.get(s, 0) + 1
        return {"total": len(self.questions), "subjects": counts}
