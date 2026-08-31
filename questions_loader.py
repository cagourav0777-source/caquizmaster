import hashlib
import json
import logging
import os
import random
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

MONTHS_MAP = {
    "jan": "January", "feb": "February", "mar": "March", "apr": "April",
    "may": "May", "jun": "June", "june": "June", "jul": "July", "july": "July",
    "aug": "August", "sep": "September", "sept": "September", "oct": "October",
    "nov": "November", "dec": "December"
}

CHAPTER_TITLES = {
    "1": "Ch 1: Nature & Scope of Business Economics",
    "2": "Ch 2: Theory of Demand & Supply",
    "3": "Ch 3: Theory of Production & Cost",
    "4": "Ch 4: Price Determination in Markets",
    "5": "Ch 5: Business Cycles",
    "6": "Ch 6: Determination of National Income",
    "7": "Ch 7: Public Finance",
    "8": "Ch 8: Money Market",
    "9": "Ch 9: International Trade",
    "10": "Ch 10: Indian Economy",
}

# 🎯 AUTO-DETECTION KEYWORDS FOR CATEGORIZATION
ECONOMICS_KEYWORDS = [
    "economics", "economy", "eco", "business", "chapter", "ch",
    "demand", "supply", "production", "market", "income", "trade",
    "mtp", "rtp", "pyq", "exam", "jan", "feb", "mar", "apr", "may",
    "jun", "jul", "aug", "sep", "oct", "nov", "dec", "sept", "july", "june"
]

ACCOUNTS_KEYWORDS = [
    "account", "accounts", "accounting", "acc", "tf", "true", "false",
    "truefalse", "true_false", "quiz", "ledger", "journal", "balance"
]

QUANT_KEYWORDS = [
    "maths", "math", "mathematics", "stats", "statistics", "quantitative",
    "quant", "qa", "aptitude", "numerical", "calculation"
]

class QuestionsManager:
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.questions: List[Dict[str, Any]] = []
        self.questions_by_source: Dict[str, List[Dict[str, Any]]] = {}
        # 🎯 NEW: Auto-categorized storage
        self.economics_sources: List[str] = []
        self.accounts_sources: List[str] = []
        self.quant_sources: List[str] = []
        self.load_questions()

    def detect_subject_category(self, filename: str) -> str:
        """
        🎯 AUTO-DETECT which subject category a file belongs to.
        Returns: "economics", "accounts", "quant", or "economics" (default)
        """
        filename_lower = filename.lower()

        # Check for Accounts keywords
        for keyword in ACCOUNTS_KEYWORDS:
            if keyword in filename_lower:
                return "accounts"

        # Check for Quant keywords
        for keyword in QUANT_KEYWORDS:
            if keyword in filename_lower:
                return "quant"

        # Check for Economics keywords (or default)
        for keyword in ECONOMICS_KEYWORDS:
            if keyword in filename_lower:
                return "economics"

        # Default to economics if no match
        return "economics"

    def format_source_title(self, source: str) -> str:
        s = source.strip()
        
        # Accounts T/F Check
        if s == "accounts_tf_last_20_attempts":
            return "Accounts: Past 20 Attempts (Exam T/F)"
        elif s == "accounts_tf":
            return "Accounts: Study Material (Module T/F)"
        elif s in ["accounts_all", "all_accounts"]:
            return "Accounts: Complete T/F Bank"
        elif any(k in s.lower() for k in ["account", "tf", "true_false", "quiz_questions"]):
            return "Accounts T/F"

        # Chapter Check
        ch_match = re.match(r"^(?:chapter|ch)[_\s]*(\d+)", s, re.I)
        if ch_match:
            ch_num = ch_match.group(1)
            return CHAPTER_TITLES.get(ch_num, f"Chapter {ch_num}")
            
        # Exam Paper / MTP Check
        exam_match = re.match(r"^([a-zA-Z0-9_\(\)]+)[_\s]*(\d{2,4})?$", s)
        if exam_match:
            clean_name = s.replace("_", " ")
            return f"{clean_name.upper()} Paper"

        return s.replace("_", " ").title()

    def parse_txt_content(self, content: str, source_name: str) -> List[Dict[str, Any]]:
        # Remove stray code block backticks if any
        clean_content = re.sub(r"```(?:text)?", "", content)
        blocks = re.split(r"\n\s*---\s*\n|\n\s*===\s*\n", clean_content)
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
                if re.match(r"^(?:Q\s*\d*[:\.\)]?|QQ+[:\.\)]?|Question:?|:?\s*\d+[\.\)])\s*", line, re.I):
                    q_text = re.sub(r"^(?:Q\s*\d*[:\.\)]?|QQ+[:\.\)]?|Question:?|:?\s*\d+[\.\)])\s*", "", line, flags=re.I).strip()
                elif re.match(r"^[A-Da-d][\)\.]\s*", line):
                    opt_text = re.sub(r"^[A-Da-d][\)\.]\s*", "", line).strip()
                    options.append(opt_text)
                elif re.match(r"^(?:Ans:?|Answer:?)\s*", line, re.I):
                    ans_char = re.sub(r"^(?:Ans:?|Answer:?)\s*", "", line, flags=re.I).strip().upper()
                elif re.match(r"^(?:Exp:?|Explanation:?)\s*", line, re.I):
                    explanation = re.sub(r"^(?:Exp:?|Explanation:?)\s*", "", line, flags=re.I).strip()
                elif re.match(r"^(?:Sub:?|Subject:?)\s*", line, re.I):
                    subject = re.sub(r"^(?:Sub:?|Subject:?)\s*", "", line, flags=re.I).strip()

            char_map = {"A": 0, "B": 1, "C": 2, "D": 3}
            clean_ans = ans_char[0] if ans_char else "A"
            correct_id = char_map.get(clean_ans, 0)

            if correct_id >= len(options):
                logger.warning(f"Invalid answer '{clean_ans}' for question: {q_text[:50]}... (has {len(options)} options)")
                correct_id = 0

            if q_text and len(options) >= 2:
                q_hash = hashlib.md5(q_text.encode("utf-8")).hexdigest()[:10]
                parsed.append({
                    "id": f"Q_{q_hash}",
                    "source": source_name,
                    "subject": subject,
                    "question": q_text,
                    "options": options,
                    "correct_option_id": correct_id,
                    "explanation": explanation,
                })

        return parsed

    def load_questions(self) -> bool:
        all_questions = []
        source_dict = {}

        if not self.data_dir.exists():
            self.data_dir.mkdir(parents=True, exist_ok=True)

        for txt_file in self.data_dir.glob("*.txt"):
            try:
                with open(txt_file, "r", encoding="utf-8") as f:
                    parsed = self.parse_txt_content(f.read(), txt_file.stem)
                    source_dict[txt_file.stem] = parsed
                    all_questions.extend(parsed)

                    # 🎯 AUTO-CATEGORIZE the file
                    category = self.detect_subject_category(txt_file.stem)
                    if category == "economics":
                        self.economics_sources.append(txt_file.stem)
                        logger.info(f"📈 Economics: {txt_file.stem}")
                    elif category == "accounts":
                        self.accounts_sources.append(txt_file.stem)
                        logger.info(f"📊 Accounts: {txt_file.stem}")
                    elif category == "quant":
                        self.quant_sources.append(txt_file.stem)
                        logger.info(f"🧮 Quantitative: {txt_file.stem}")
            except Exception as e:
                logger.error(f"Error reading {txt_file}: {e}")

        for json_file in self.data_dir.glob("*.json"):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    json_data = json.load(f)
                    if isinstance(json_data, list):
                        parsed_json = []
                        for item in json_data:
                            if item.get("question") and isinstance(item.get("options"), list):
                                if "id" not in item:
                                    item["id"] = "Q_" + hashlib.md5(item["question"].encode()).hexdigest()[:10]
                                item["source"] = json_file.stem
                                parsed_json.append(item)
                                all_questions.append(item)
                        source_dict[json_file.stem] = parsed_json

                        # 🎯 AUTO-CATEGORIZE the JSON file
                        category = self.detect_subject_category(json_file.stem)
                        if category == "economics":
                            self.economics_sources.append(json_file.stem)
                            logger.info(f"📈 Economics: {json_file.stem}")
                        elif category == "accounts":
                            self.accounts_sources.append(json_file.stem)
                            logger.info(f"📊 Accounts: {json_file.stem}")
                        elif category == "quant":
                            self.quant_sources.append(json_file.stem)
                            logger.info(f"🧮 Quantitative: {json_file.stem}")
            except Exception as e:
                logger.error(f"Error reading {json_file}: {e}")

        unique_dict = {}
        for q in all_questions:
            if 2 <= len(q["options"]) <= 10:
                unique_dict[q["id"]] = q

        self.questions = list(unique_dict.values())
        self.questions_by_source = source_dict

        logger.info(f"✅ Total unique questions loaded: {len(self.questions)}")
        logger.info(f"📈 Economics files: {len(self.economics_sources)}")
        logger.info(f"📊 Accounts files: {len(self.accounts_sources)}")
        logger.info(f"🧮 Quant files: {len(self.quant_sources)}")

        return len(self.questions) > 0

    def get_available_chapters(self) -> List[Tuple[str, str, int]]:
        ch_list = []
        for src, q_list in self.questions_by_source.items():
            if re.match(r"^(?:chapter|ch)", src, re.I):
                title = self.format_source_title(src)
                ch_match = re.search(r"\d+", src)
                num = int(ch_match.group()) if ch_match else 999
                ch_list.append((num, src, title, len(q_list)))
        ch_list.sort(key=lambda x: x[0])
        return [(src, title, count) for _, src, title, count in ch_list]

    def get_available_pyqs(self) -> List[Tuple[str, str, int]]:
        """Returns Economics Past Papers / MTPs only (Excludes Chapters and Accounts)."""
        pyq_list = []
        for src in self.economics_sources:
            # Skip chapters
            if re.match(r"^(?:chapter|ch)", src, re.I):
                continue
            q_list = self.questions_by_source.get(src, [])
            if q_list:
                title = self.format_source_title(src)
                pyq_list.append((src, title, len(q_list)))
        pyq_list.sort(key=lambda x: x[0])
        return pyq_list

    def get_accounts_questions(self) -> List[Dict[str, Any]]:
        """Gathers all Accounts True/False questions from auto-detected accounts files."""
        acc_pool = []
        for src in self.accounts_sources:
            acc_pool.extend(self.questions_by_source.get(src, []))
        return acc_pool

    def get_quant_questions(self) -> List[Dict[str, Any]]:
        """🎯 NEW: Gathers all Quantitative Aptitude questions from auto-detected files."""
        quant_pool = []
        for src in self.quant_sources:
            quant_pool.extend(self.questions_by_source.get(src, []))
        return quant_pool

    def get_economics_questions(self) -> List[Dict[str, Any]]:
        """🎯 NEW: Gathers all Economics questions from auto-detected files."""
        eco_pool = []
        for src in self.economics_sources:
            eco_pool.extend(self.questions_by_source.get(src, []))
        return eco_pool

    def get_total_count_for_target(self, target_key: str) -> int:
        if target_key in ["accounts_all", "all_accounts"]:
            return len(self.get_accounts_questions())
        elif target_key in ["quant_all", "all_quant"]:
            return len(self.get_quant_questions())
        elif target_key in self.questions_by_source:
            return len(self.questions_by_source[target_key])
        elif target_key in ["all", "all_mixed"]:
            return len(self.questions)
        elif target_key == "all_chapters":
            return len([q for q in self.questions if re.match(r"^(?:chapter|ch)", q.get("source", ""), re.I)])
        elif target_key == "all_pyqs":
            return len(self.get_economics_questions()) - len([q for q in self.questions if re.match(r"^(?:chapter|ch)", q.get("source", ""), re.I)])
        else:
            return len([q for q in self.questions if target_key.lower() in q.get("subject", "").lower()])

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

    def get_mocktest_questions(self, target_key: str, count: int) -> List[Dict[str, Any]]:
        if target_key in ["accounts_all", "all_accounts"]:
            pool = list(self.get_accounts_questions())
        elif target_key in ["quant_all", "all_quant"]:
            pool = list(self.get_quant_questions())
        elif target_key in self.questions_by_source:
            pool = list(self.questions_by_source[target_key])
        elif target_key in ["all", "all_mixed"]:
            pool = list(self.questions)
        elif target_key == "all_chapters":
            pool = [q for q in self.questions if re.match(r"^(?:chapter|ch)", q.get("source", ""), re.I)]
        elif target_key == "all_pyqs":
            pool = list(self.get_economics_questions())
            # Remove chapters from economics
            pool = [q for q in pool if not re.match(r"^(?:chapter|ch)", q.get("source", ""), re.I)]
        else:
            pool = [q for q in self.questions if target_key.lower() in q.get("subject", "").lower()]

        if not pool:
            pool = list(self.questions)

        random.shuffle(pool)
        return pool[:count]

    def get_stats(self) -> Dict[str, Any]:
        counts: Dict[str, int] = {}
        for q in self.questions:
            s = q.get("subject", "General")
            counts[s] = counts.get(s, 0) + 1
        return {"total": len(self.questions), "subjects": counts}
