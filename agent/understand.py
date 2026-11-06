# ==========================================
# DMart Regional Director Assistant
# Component 1: Question Interpreter
# File: agent/understand.py
# ==========================================

import re
from difflib import SequenceMatcher


# 1. RECOGNISED STORES
STORES = [
    "Mumbai",
    "Pune",
    "Hyderabad",
    "Bengaluru",
    "Ahmedabad"
]

# Store aliases
STORE_ALIASES = {
    "bangalore": "Bengaluru"
}


# 2. RECOGNISED PRODUCTS
PRODUCTS = [
    "Amul Milk",
    "Basmati Rice",
    "Detergent Powder",
    "Glucose Biscuits",
    "Instant Noodles",
    "Iodised Salt",
    "Sunflower Oil",
    "Toor Dal"
]


# 3. RECOGNISED METRICS
METRIC_SYNONYMS = {
    "revenue": "revenue_inr",
    "sales": "revenue_inr",
    "turnover": "revenue_inr",
    "earnings": "revenue_inr",

    "target": "daily_target_inr",

    "footfall": "footfall",
    "visitors": "footfall",

    "stockout": "stockout_hours",
    "discount": "discount_pct"
}


# 4. UNSUPPORTED METRICS
UNSUPPORTED_METRICS = [
    "profit",
    "margin",
    "marketing",
    "cost",
    "expense",
    "shortfall",
    "efficiency",
    "weekend",
    "per footfall",
    "per visitor"
]


# 5. INTERPRETER CONFIGURATION
from datetime import datetime, timedelta
AS_OF_DATE = "2026-06-30"

MIN_FUZZY_MATCH_SCORE = 0.70


# ==========================================
# STORE RECOGNITION
# ==========================================


# Words that should not be interpreted as store names
STORE_STOP_WORDS = {
    "hello", "thanks", "thank", "kindly", "please",
    "display", "compare", "which", "what", "whats",
    "how", "why", "did", "and", "show", "check",
    "report", "where", "would", "could", "can",
    "will", "give", "tell", "list"
}

PROPER_NOUN_EXCLUSIONS = {
    "dmart", "avenue", "supermarts", "kavita", "rao",
    "meteo", "github", "python", "sqlite", "postgresql",
    "markdown", "pure", "ahead", "plunge", "pane", "ahmed"
}

BRIEF_PROPER_NOUNS = {
    "dmart", "avenue", "supermarts", "kavita", "rao",
    "meteo", "github", "python", "sqlite",
    "postgresql", "markdown"
}

NEVER_STORE_WORDS = {
    "pure", "ahead", "plunge", "pane", "ahmed"
}


def find_unresolved_store_candidate(question, resolved_store=None):
    """Identifies an unresolved named-store candidate."""

    tokens = re.findall(r"[A-Za-z]+(?:'[sS])?", question)

    recognised_names = {
        store.lower() for store in STORES
    } | set(STORE_ALIASES.keys())

    for index, token in enumerate(tokens):
        clean = token.lower().replace("'s", "")
        possessive = token.lower().endswith("'s")

        if clean in recognised_names:
            continue

        if len(clean) < 5:
            continue

        if clean in NEVER_STORE_WORDS:
            continue

        previous = tokens[index - 1].lower() if index > 0 else ""

        # Special handling for the brief's proper nouns.
        if clean in BRIEF_PROPER_NOUNS:
            if possessive or previous in {"for", "about", "in", "at"}:
                return token
            continue

        if clean in STORE_STOP_WORDS:
            continue

        if clean in PROPER_NOUN_EXCLUSIONS:
            continue

        if index == 0 and not possessive:
            continue

        if token[0].islower() and not possessive:
            if previous in {"about", "in", "at"}:
                return token
            continue

        if possessive or previous in {
            "for", "about", "in", "at",
          "and", "or", "vs", "versus", "than"
        }:
            return token

    return None

def find_store(question):
    """Identifies a store and returns its resolution confidence."""

    text = question.lower()
    resolved_matches = {}

    # 1. Exact store matches
    for store in STORES:
        pattern = r"\b" + re.escape(store.lower()) + r"\b"

        if re.search(pattern, text):
            resolved_matches[store] = {
                "confidence": 1.0,
                "status": "exact"
            }

    # 2. Alias matches
    for alias, actual_store in STORE_ALIASES.items():
        pattern = r"\b" + re.escape(alias) + r"\b"

        if re.search(pattern, text):
            resolved_matches[actual_store] = {
                "confidence": 1.0,
                "status": "alias"
            }

    # 3. Fuzzy matches
    words = re.findall(r"\b[A-Za-z]+(?:'s)?\b", question)

    for index, word in enumerate(words):
        clean_word = word.lower().replace("'s", "")
        possessive = word.lower().endswith("'s")

        if len(clean_word) < 5:
            continue

        if clean_word in STORE_STOP_WORDS:
            continue

        if clean_word in PROPER_NOUN_EXCLUSIONS:
            continue

        if index == 0 and not possessive:
            continue

        if word[0].islower() and not possessive:
            continue

        scores = [
            (
                SequenceMatcher(None, clean_word, store.lower()).ratio(),
                store
            )
            for store in STORES
        ]

        best_score, best_store = max(scores)

        if best_score >= MIN_FUZZY_MATCH_SCORE:
            existing = resolved_matches.get(best_store)

            if existing is None or best_score > existing["confidence"]:
                resolved_matches[best_store] = {
                    "confidence": round(best_score, 2),
                    "status": "fuzzy"
                }

    # 4. Multiple distinct resolved stores
    if len(resolved_matches) > 1:
        return {
            "store": None,
            "confidence": 0.4,
            "status": "ambiguous"
        }

    # 5. One resolved store
    if len(resolved_matches) == 1:
        store, details = next(iter(resolved_matches.items()))

        return {
            "store": store,
            "confidence": details["confidence"],
            "status": details["status"]
        }

    # 6. Unresolved candidate
    candidate = find_unresolved_store_candidate(question)

    if candidate:
        return {
            "store": None,
            "confidence": 0.4,
            "status": "unresolved"
        }

    # 7. No store mentioned
    return {
        "store": None,
        "confidence": 1.0,
        "status": "none"
    }


def find_product(question):
    """Identifies an approved product in the question."""

    question_lower = question.lower()

    for product in PRODUCTS:
        product_words = product.lower().split()

        # Match the product name without its size suffix.
        product_name = " ".join(product_words)

        if product_name in question_lower:
            return {
                "product": product,
                "confidence": 1.0,
                "status": "exact"
            }

    return {
        "product": None,
        "confidence": 1.0,
        "status": "none"
    }



def find_metric(question):
    """Identifies an approved or unsupported metric in a question."""

    question_lower = question.lower().replace("_", " ")

    # 1. Check unsupported metrics first.
    for unsupported in UNSUPPORTED_METRICS:

        if unsupported == "expense":
            pattern = r"\bexpenses?\b"

        elif unsupported == "per visitor":
            pattern = r"\bper\s+visitors?\b"

        else:
            pattern = (
                r"\b"
                + re.escape(unsupported).replace(r"\ ", r"\s+")
                + r"\b"
            )

        if re.search(pattern, question_lower):
            return {
                "metric": None,
                "confidence": 1.0,
                "status": "unsupported"
            }

    # 2. Check approved metric synonyms.
    for synonym, standard_metric in METRIC_SYNONYMS.items():

        pattern = r"\b" + re.escape(synonym) + r"\b"

        if re.search(pattern, question_lower):
            return {
                "metric": standard_metric,
                "confidence": 1.0,
                "status": "exact"
            }

    # 3. No metric identified.
    return {
        "metric": None,
        "confidence": 1.0,
        "status": "none"
    }

def find_weekday(question):
    """Identifies weekday names in a question."""

    weekdays = [
        "monday", "tuesday", "wednesday",
        "thursday", "friday", "saturday", "sunday"
    ]

    found_weekdays = []

    for weekday in weekdays:
        if re.search(
            r"\b" + weekday + r"s?\b",
            question,
            re.IGNORECASE
        ):
            found_weekdays.append(weekday)

    return found_weekdays

def validate_weekday(weekday, date_text):
    """Checks whether a weekday matches a calendar date."""

    parsed_date = datetime.strptime(
        date_text, "%Y-%m-%d"
    ).date()

    actual_weekday = parsed_date.strftime("%A").lower()

    return weekday.lower() == actual_weekday

def find_date(question):
    """Identifies a supported date or date range."""

    # 1. Detect unsupported date expressions.
    unsupported_date_patterns = [
        r"\btomorrow\b",
        r"\btoday\b",
        r"\blast\s+week\b",
        r"\bnext\s+week\b",
        r"\blast\s+month\b",
        r"\bnext\s+month\b",
        r"\bfrom\s+.+?\s+to\s+.+",

        # Abbreviated month names
        r"\b\d{1,2}\s+(?:Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.?\s+\d{4}\b",

        # Date without year
        r"\b\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\b(?!\s+\d{4})",

        # Compact numeric dates
        r"\b\d{8}\b",
      ]

    for pattern in unsupported_date_patterns:
      if re.search(pattern, question, re.IGNORECASE):
        return {
          "date": None,
          "start_date": None,
          "end_date": None,
          "confidence": 0.4,
          "status": "unresolved"
        }

    # 2. Date range: between DATE and DATE
    range_match = re.search(
        r"\bbetween\s+(\d{4}-\d{2}-\d{2})\s+and\s+(\d{4}-\d{2}-\d{2})\b",
        question,
        re.IGNORECASE
    )

    if range_match:
        start_text, end_text = range_match.groups()

        try:
            start_date = datetime.strptime(
                start_text, "%Y-%m-%d"
            ).date()

            end_date = datetime.strptime(
                end_text, "%Y-%m-%d"
            ).date()

            if start_date > end_date:
                raise ValueError("Reversed date range")

            return {
                "date": None,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "confidence": 1.0,
                "status": "range"
            }

        except ValueError:
            return {
                "date": None,
                "start_date": None,
                "end_date": None,
                "confidence": 0.4,
                "status": "unresolved"
            }

    # 3. Yesterday
    if re.search(r"\byesterday\b", question, re.IGNORECASE):
        reference_date = datetime.strptime(
            AS_OF_DATE, "%Y-%m-%d"
        ).date()

        yesterday = reference_date - timedelta(days=1)

        return {
            "date": yesterday.isoformat(),
            "start_date": None,
            "end_date": None,
            "confidence": 1.0,
            "status": "exact"
        }

    # 4. ISO date
    iso_dates = re.findall(
        r"\b\d{4}-\d{2}-\d{2}\b",
        question
    )

    for date_text in iso_dates:
        try:
            parsed_date = datetime.strptime(
                date_text, "%Y-%m-%d"
            ).date()

            return {
                "date": parsed_date.isoformat(),
                "start_date": None,
                "end_date": None,
                "confidence": 1.0,
                "status": "exact"
            }

        except ValueError:
            return {
                "date": None,
                "start_date": None,
                "end_date": None,
                "confidence": 0.4,
                "status": "unresolved"
            }

    # 5. Written date
    written_dates = re.findall(
        r"\b\d{1,2}\s+[A-Za-z]+\s+\d{4}\b",
        question
    )

    for date_text in written_dates:
        try:
            parsed_date = datetime.strptime(
                date_text, "%d %B %Y"
            ).date()

            return {
                "date": parsed_date.isoformat(),
                "start_date": None,
                "end_date": None,
                "confidence": 1.0,
                "status": "exact"
            }

        except ValueError:
            return {
                "date": None,
                "start_date": None,
                "end_date": None,
                "confidence": 0.4,
                "status": "unresolved"
            }

    return {
        "date": None,
        "start_date": None,
        "end_date": None,
        "confidence": 1.0,
        "status": "none"
    }
    
