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

def _find_date_without_weekday(question):
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

def find_date(question):
    """Identifies dates and validates weekday references."""

    # First, run the existing date recognition logic.
    result = _find_date_without_weekday(question)

    # Identify weekday references.
    weekdays = find_weekday(question)

    # No weekday mentioned: retain the original result.
    if not weekdays:
        return result

    # Check whether any weekday is plural (e.g. Mondays).
    has_plural_weekday = any(
        re.search(
            r"\b" + weekday + r"s\b",
            question,
            re.IGNORECASE
        )
        for weekday in weekdays
    )

    # Plural weekdays are permitted with valid date ranges.
    if result["status"] == "range" and has_plural_weekday:
        return result

    # For a single date, validate the weekday.
    if result["status"] == "exact" and len(weekdays) == 1:

        if not has_plural_weekday and validate_weekday(
            weekdays[0], result["date"]
        ):
            return result

    # All other weekday/date combinations are unresolved.
    return {
        "date": None,
        "start_date": None,
        "end_date": None,
        "confidence": 0.4,
        "status": "unresolved"
    }



# ==========================================
# INTENT CLASSIFICATION AND ENTITY RESOLUTION
# ==========================================

INTENTS = {
    "lookup",
    "target_vs_actual",
    "comparison",
    "inventory",
    "feedback",
    "weather",
    "unsupported_metric",
    "out_of_scope",
    "diagnostic"
}

INTENT_PATTERNS = {
    "out_of_scope": [
        r"\b(?:reorder|place an order|purchase|buy stock|send (?:an )?(?:email|message| alert)|message the|contact the)\b",
        r"\b(?:change|update|delete|modify)\b.*\b(?:record|data|inventory|stock)\b"
    ],
    "diagnostic": [
        r"\bwhy\b", r"\bwhat caused\b", r"\breason for\b",
        r"\broot cause\b", r"\btrend\b", r"\bexplain (?:the )?(?:increase|decrease|drop|rise|change)\b",
        r"\bwhat is driving\b", r"\bdriver(?:s)? of\b"
    ],
    "inventory": [
        r"\binventory\b", r"\bstock(?: level| availability| status)?\b",
        r"\b(?:available|remaining) units?\b", r"\bproduct\b",
        r"\b(?:out of stock|stockout)\b"
    ],
    "feedback": [
        r"\bfeedback\b", r"\breviews?\b", r"\bratings?\b",
        r"\bcustomer sentiment\b", r"\bwhat (?:are )?customers saying\b",
        r"\bcustomer comments?\b"
    ],
    "target_vs_actual": [
        r"\btarget\b.*\b(?:hit|met|meet|miss|missed|beat|exceed|exceeded|achieve|achieved|reach|reached|below|above|against|versus)\b",
        r"\b(?:hit|met|meet|miss|missed|beat|exceed|exceeded|achieve|achieved|reach|reached|below|above|against|versus)\b.*\btarget\b",
        r"\bfall short\b", r"\bachievement\b",
        r"\bactual vs\.? target\b", r"\btarget vs\.? actual\b",
        r"\bperformance band\b"
    ],
    "comparison": [
        r"\bcompare\b", r"\bcomparison\b", r"\bversus\b",
        r"\bvs\.?\b", r"\bacross (?:all )?stores\b",
        r"\bwhich store\b", r"\brank(?:ing)?\b"
    ],
    "weather": [
        r"\bweather\b", r"\brain(?:fall|ing)?\b",
        r"\btemperature\b", r"\bhumidity\b",
        r"\bhot\b", r"\bcold\b"
    ]
}


def find_intent(question, context=None):
    """Classifies a question using the agreed intent precedence."""

    text = question.lower().strip()
    metric_result = find_metric(question)

    # A target-check follow-up can consist only of a new store or date.
    previous_target = bool(
        context and context.get("target_followup")
    )
    has_store_or_date = (
        find_store(question)["status"] != "none"
        or find_date(question)["status"] != "none"
    )
    has_strong_new_intent = any(
        re.search(pattern, text)
        for intent, patterns in INTENT_PATTERNS.items()
        if intent not in {"target_vs_actual", "comparison"}
        for pattern in patterns
    )
    if (
        previous_target
        and has_store_or_date
        and not metric_result["status"] == "unsupported"
        and not has_strong_new_intent
        and not re.search(r"\b(?:compare|comparison|versus|vs)\b", text)
    ):
        return "target_vs_actual"

    # 1. Prohibited actions override analytical intent.
    if any(re.search(p, text) for p in INTENT_PATTERNS["out_of_scope"]):
        return "out_of_scope"

    # 2. Unsupported metrics override approved metric words.
    if metric_result["status"] == "unsupported":
        return "unsupported_metric"

    # 3. Diagnostic questions.
    if any(re.search(p, text) for p in INTENT_PATTERNS["diagnostic"]):
        return "diagnostic"

    # 4-7. Domain-specific intents.
    for intent in (
        "inventory", "feedback", "target_vs_actual", "comparison"
    ):
        if any(re.search(p, text) for p in INTENT_PATTERNS[intent]):
            return intent

    # 8. A recognised metric indicates a lookup.
    if metric_result["metric"] is not None:
        return "lookup"

    # 9. Weather.
    if any(re.search(p, text) for p in INTENT_PATTERNS["weather"]):
        return "weather"

    # 10. A named store/date without a metric is treated as a lookup.
    store_result = find_store(question)
    date_result = find_date(question)
    if (
        store_result["status"] != "none"
        or date_result["status"] != "none"
    ):
        return "lookup"

    return "out_of_scope"


REQUIRED_ENTITIES = {
    "lookup": ("store", "metric", "date"),
    "target_vs_actual": ("store", "date"),
    "comparison": ("metric", "date"),
    "inventory": ("product",),
    "feedback": ("store",),
    "weather": ("store", "date"),
    "unsupported_metric": (),
    "out_of_scope": (),
    "diagnostic": ()
}


def _entity_is_unresolved(result):
    return result.get("status") in {"unresolved", "ambiguous"}


def _clarification_for(missing, unresolved):
    """Builds a concise clarification prompt from missing entities."""
    parts = []

    if "store" in unresolved:
        parts.append("the store name")
    elif "store" in missing:
        parts.append("a store")

    if "metric" in missing:
        parts.append("the metric (for example, revenue or footfall)")
    if "date" in unresolved:
        parts.append("a supported date or date range")
    elif "date" in missing:
        parts.append("a date or date range")
    if "product" in unresolved:
        parts.append("the product name")
    elif "product" in missing:
        parts.append("a product name")

    if not parts:
        return None
    if len(parts) == 1:
        return "Please clarify " + parts[0] + "."
    return "Please clarify " + ", ".join(parts[:-1]) + " and " + parts[-1] + "."


def understand(question, context=None):
    """
    Interprets a question and resolves the entities required by its intent.

    Context is a mutable dictionary scoped to one conversation/session.
    The returned context should be passed to the next call in that session.
    """

    if not isinstance(question, str) or not question.strip():
        return {
            "intent": "out_of_scope",
            "entities": {},
            "missing_entities": [],
            "unresolved_entities": [],
            "confidence": 1.0,
            "needs_clarification": False,
            "clarification_question": None,
            "context": dict(context or {})
        }

    session = dict(context or {})
    intent = find_intent(question, session)

    store_result = find_store(question)
    product_result = find_product(question)
    metric_result = find_metric(question)
    date_result = find_date(question)

    entities = {
        "store": store_result["store"],
        "product": product_result["product"],
        "metric": metric_result["metric"],
        "date": date_result["date"],
        "start_date": date_result["start_date"],
        "end_date": date_result["end_date"]
    }

    results = {
        "store": store_result,
        "product": product_result,
        "metric": metric_result,
        "date": date_result
    }

    # Only entities used by this intent can block execution. An irrelevant
    # unresolved entity must not trigger clarification or affect confidence.
    required = REQUIRED_ENTITIES[intent]
    unresolved = []
    for name, result in results.items():
        if name in required and _entity_is_unresolved(result):
            unresolved.append(name)

    # A date range is represented by start_date/end_date, not date.
    date_present = date_result["status"] in {"exact", "range"}
    date_explicitly_unresolved = date_result["status"] == "unresolved"

    # Context inheritance is limited to entities required by this intent.
    if intent not in {"unsupported_metric", "diagnostic", "out_of_scope"}:
        if "store" in required and store_result["status"] == "none":
            if session.get("store"):
                entities["store"] = session["store"]
                results["store"] = {
                    "store": session["store"],
                    "confidence": 1.0,
                    "status": "context"
                }

        if "metric" in required and metric_result["status"] == "none":
            if session.get("metric"):
                entities["metric"] = session["metric"]
                results["metric"] = {
                    "metric": session["metric"],
                    "confidence": 1.0,
                    "status": "context"
                }

        if "date" in required and date_result["status"] == "none":
            if (
                session.get("date")
                or (session.get("start_date") and session.get("end_date"))
            ):
                entities["date"] = session.get("date")
                entities["start_date"] = session.get("start_date")
                entities["end_date"] = session.get("end_date")
                results["date"] = {
                    "date": session["date"],
                    "start_date": session.get("start_date"),
                    "end_date": session.get("end_date"),
                    "confidence": 1.0,
                    "status": "context"
                }

    # Target-vs-actual and weather require one date. This also rejects a
    # date range inherited from the previous turn in the same session.
    if intent in {"target_vs_actual", "weather"} and (
        entities.get("start_date") or entities.get("end_date")
    ):
        unresolved.append("date")
        entities["date"] = None
        entities["start_date"] = None
        entities["end_date"] = None
        results["date"] = {
            "date": None, "start_date": None, "end_date": None,
            "confidence": 0.4, "status": "unresolved"
        }

    # Required fields not supplied or inherited are missing.
    missing = []
    for name in required:
        if name == "date":
            if not entities.get("date") and not (
                entities.get("start_date") and entities.get("end_date")
            ) and "date" not in unresolved:
                missing.append("date")
        elif not entities.get(name) and name not in unresolved:
            missing.append(name)

    # Comparison is across stores; it must not inherit a store.
    if intent == "comparison":
        entities["store"] = None

    # An explicitly unresolved entity blocks context fallback and clarification.
    unresolved = list(dict.fromkeys(unresolved))
    confidence_values = []
    for name in required:
        result = results[name]
        if name == "date" and result["status"] == "range":
            confidence_values.append(result["confidence"])
        elif result["status"] == "none":
            # Missing required entities are assigned the clarification floor.
            confidence_values.append(0.4 if name in missing else 1.0)
        else:
            confidence_values.append(result["confidence"])

    confidence = min(confidence_values) if confidence_values else 1.0
    needs_clarification = bool(missing or unresolved or confidence < 0.7)

    # Store only resolved entities that this intent actually used.
    if intent not in {"unsupported_metric", "diagnostic", "out_of_scope"}:
        if "store" in required:
            if store_result["status"] in {"exact", "alias", "fuzzy"}:
                session["store"] = store_result["store"]
            elif store_result["status"] in {"unresolved", "ambiguous"}:
                session.pop("store", None)

        if "metric" in required:
            if metric_result["status"] == "exact":
                session["metric"] = metric_result["metric"]
            elif metric_result["status"] == "unsupported":
                session.pop("metric", None)

        if "date" in required:
            if date_result["status"] in {"exact", "range"}:
                session["date"] = date_result["date"]
                session["start_date"] = date_result["start_date"]
                session["end_date"] = date_result["end_date"]
            elif date_explicitly_unresolved:
                session.pop("date", None)
                session.pop("start_date", None)
                session.pop("end_date", None)

        if "product" in required and product_result["status"] == "exact":
            session["product"] = product_result["product"]

        session["last_intent"] = intent
        session["target_followup"] = intent == "target_vs_actual"

    return {
        "intent": intent,
        "entities": entities,
        "missing_entities": missing,
        "unresolved_entities": unresolved,
        "confidence": round(confidence, 2),
        "needs_clarification": needs_clarification,
        "clarification_question": _clarification_for(missing, unresolved)
            if needs_clarification else None,
        "context": session
    }
