"""Deterministic pre-LLM safety guardrails and risky-action confirmation helpers."""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class SafetyResult:
    allowed: bool
    reason: str = ""
    reply: str = ""


INJECTION_PATTERNS = [
    re.compile(r"\b(ignore|forget|disregard|override)\b.{0,30}\b(previous|prior|above|all|your)\b.{0,25}\b(instructions|rules|prompt)\b", re.I),
    re.compile(r"\b(reveal|show|print|dump|leak|output|repeat)\b.{0,30}\b(system prompt|hidden prompt|hidden instructions|instructions above|prompt above|api[_\s]?key|env|database|secret)\b", re.I),
    re.compile(r"\bwhat\s+(?:is|are)\s+your\s+(?:system prompt|hidden instructions|hidden prompt|internal rules)\b", re.I),
    re.compile(r"\b(system override|developer mode|dan mode|jailbreak|bypass safety|no rules)\b", re.I),
    re.compile(r"\b(?:act\s+as|you\s+are\s+now)\s+(?:an?\s+)?(?:unrestricted|admin|linux|root|hacker|dan)\b", re.I),
    re.compile(r"\b(set|change|override)\b.{0,30}\bprice\b.{0,20}\bto\b", re.I),
    re.compile(r"\b(?:100%\s+discount|make\s+(?:it|this|everything|the\s+price)\s+free)\b", re.I),
    re.compile(r"(?:\bdrop\s+table\b|\bunion\s+select\b|;\s*delete\s+from\b|'\s*or\s*1\s*=\s*1)", re.I),
]

CROSS_USER_PATTERNS = [
    re.compile(r"\b(other|another|all)\s+users?\b.{0,30}\b(orders?|data|memories|preferences?|address(?:es)?)\b", re.I),
    re.compile(
        r"\b(orders?|preferences?|memories|address(?:es)?|data)\s+(?:for|of)\s+(?:user[_\s-]?id\s+)?"
        r"(?!me\b|my\b|myself\b|this\b|the\b|our\b|khaas\b|studio\b|store\b|shop\b|kurta\b|kurtas\b|shirt\b|shirts\b|dupatta\b|shawl\b|item\b|items\b|product\b|products\b|delivery\b|shipping\b)"
        r"[a-z0-9_-]{3,}\b",
        re.I,
    ),
    re.compile(r"\buser[_\s-]?id\s*[=:]?\s*[a-z0-9_-]{3,}\b", re.I),
    re.compile(r"\b(?:show|tell|give|list|get)\b.{0,20}\b(?!my\b|our\b|khaas\b|store\b)[a-z0-9_-]{3,}'s\s+(?:orders?|preferences?|memories|address(?:es)?|size|data)\b", re.I),
    re.compile(r"\bwhat\s+(?:did|size\s+does)\s+(?!i\b|you\b|khaas\b)[a-z0-9_-]{3,}\s+(?:order|buy|wear)\b", re.I),
]

OFF_TOPIC_PATTERNS = [
    re.compile(r"\b(write|generate|create)\b.{0,25}\b(python|javascript|java|c\+\+|html|sql|code|script|scraper|malware)\b", re.I),
    re.compile(r"\b(quantum computing|web scraper|calculus|homework|write an essay|stock market|crypto price|medical diagnosis|prescribe)\b", re.I),
    re.compile(r"\b(?:what\s+is\s+the\s+)?(?:capital|president|prime\s+minister)\s+of\b", re.I),
    re.compile(r"\btell\s+me\s+a\s+joke\b", re.I),
    re.compile(r"\bwrite\s+(?:a\s+|me\s+a\s+)?(?:poem|story|song|essay)\b", re.I),
    re.compile(r"\b(?:recipe\s+for|weather\s+in)\b", re.I),
    re.compile(r"\bexplain\s+(?:world\s+war|quantum|relativity|photosynthesis|calculus)\b", re.I),
    re.compile(r"\btranslate\s+.{1,40}\s+(?:to|into)\s+(?:french|spanish|german|arabic|urdu)\b", re.I),
]

CONFIRMATION_PATTERN = re.compile(
    r"\b(yes|confirm|confirmed|go ahead|proceed|place (?:the |this )?order|place it|book it|do it|cancel it|sure)\b",
    re.I,
)
NEGATION_PATTERN = re.compile(
    r"\b(no|not|don'?t|do\s+not|never|wait|hold\s+on|stop|changed\s+my\s+mind)\b",
    re.I,
)


def evaluate_safety(message: str) -> SafetyResult:
    """Run zero-token deterministic checks before invoking Claude."""
    text = (message or "").strip()
    if not text:
        return SafetyResult(
            allowed=False,
            reason="empty_message",
            reply="Please type a question about Khaas Studio products, sizing, or your orders.",
        )

    for pattern in INJECTION_PATTERNS:
        if pattern.search(text):
            return SafetyResult(
                allowed=False,
                reason="prompt_injection",
                reply=(
                    "I cannot follow instruction overrides, reveal internal prompts, or alter store pricing. "
                    "I can only help you browse Khaas Studio items, check sizing, or manage your own orders."
                ),
            )

    for pattern in CROSS_USER_PATTERNS:
        if pattern.search(text):
            return SafetyResult(
                allowed=False,
                reason="cross_user_isolation",
                reply=(
                    "For privacy and security, I can only access orders and preferences belonging to your own active account."
                ),
            )

    for pattern in OFF_TOPIC_PATTERNS:
        if pattern.search(text):
            return SafetyResult(
                allowed=False,
                reason="off_topic",
                reply=(
                    "I'm ShopBot for Khaas Studio, so I only help with our clothing, accessories, sizing, "
                    "and orders. Ask me about kurtas, dupattas, stock, or delivery!"
                ),
            )

    return SafetyResult(allowed=True)


def has_user_confirmation(message: str) -> bool:
    """Check whether the user's current turn explicitly confirms a risky DB mutation."""
    text = (message or "").strip()
    if not text or NEGATION_PATTERN.search(text):
        return False
    return bool(CONFIRMATION_PATTERN.search(text))
