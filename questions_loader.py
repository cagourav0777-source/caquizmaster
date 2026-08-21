import json
import logging
import os
import random
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

class QuestionsManager:
    def __init__(self, txt_path: str = "data/questions.txt", json_path: str = "data/questions.json"):
        self.txt_path = Path(txt_path)
        self.json_path = Path(json_path)
        self.questions: List[Dict[str, Any]] = []
        self.load_questions()

    def parse_txt_file(self) -> List[Dict[str, Any]]:
        """Parses human-friendly questions.txt format."""
        if not self.txt_path.exists():
            return []

        with open(self.txt_path, "r", encoding="utf-8") as f:
            content = f.read()

        blocks = re.split(r"\n\s*---\s*\n|\n\s*===\s*\n", content)
        parsed = []

        for idx, block in enumerate(blocks):
            lines = [l.strip() for l in block.strip().split("\n") if l.strip()]
            if not lines:
                continue

            q_text = ""
            options = []
            ans_char = ""
            explanation = ""
            subject = "CA Foundation"

            for line in lines:
                if re.match(r"^(Q:|Question:)\s*", line, re.I):
                    q_text = re.sub(r"^(Q:|Question:)\s*", "", line, flags=re.I).strip()
                elif re.match(r"^[A-Da-d][\)\.]\s*", line):
                    opt_text = re.sub(r"^[A-Da-d][\)\.]\s*", "", line).strip()
                    options.append(opt_text)
                elif re.match(r"^(Ans:|Answer:)\s*", line, re.I):
                    ans_char = re.sub(r"^(Ans:|Answer:)\s*", "", line, flags=re.I).strip().upper()
                elif re.match(r"^(Exp:|Explanation:)\s*", line, re.I):
                    explanation = re.sub(r"^(Exp:|Explanation:)\s*", "", line, flags=re.I).strip()
                elif re.match(r"^(Sub:|Subject:)\s*", line, re.I):
                    subject = re.sub(r"^(Sub:|Subject:)\s*", "", line, flags=re.I).strip()

            # Map Answer A, B, C, D to 0, 1, 2, 3
            char_map = {"A": 0, "B": 1, "C": 2, "D": 3}
            correct_id = char_map.get(ans_char[0] if ans_char else "", 0)

            if q_text and len(options) >= 2:
                parsed.append({
                    "id": f"TXT_Q_{idx+1}",
                    "subject": subject,
                    "question": q_text,
                    "options": options,
                    "correct_option_id": correct_id,
                    "explanation": explanation,
                })

        return parsed

    def load_questions(self) -> bool:
        """Loads from questions.txt first, then fallback/merges with questions.json."""
        all_questions = []

        # 1. Load from TXT if available
        txt_questions = self.parse_txt_file()
        all_questions.extend(txt_questions)

        # 2. Load from JSON if available
        if self.json_path.exists():
            try:
                with open(self.json_path, "r", encoding="utf-8") as f:
                    json_data = json.load(f)
                    for item in json_data:
                        if item.get("question") and isinstance(item.get("options"), list):
                            all_questions.append(item)
            except Exception as e:
                logger.error(f"Error loading questions.json: {e}")

        # Filter valid questions
        self.questions = [
            q for q in all_questions
            if q.get("question") and isinstance(q.get("options"), list) and 2 <= len(q["options"]) <= 10
        ]
        logger.info(f"Total questions loaded: {len(self.questions)} (from TXT: {len(txt_questions)})")
        return len(self.questions) > 0

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
            s = q.get("subject", "General")
            counts[s] = counts.get(s, 0) + 1
        return {"total": len(self.questions), "subjects": counts}
