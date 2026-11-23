"""Grounded document-chat query rewriting and answer generation."""

from __future__ import annotations

import re
from typing import Any

from app.utils.model_provider import ModelProvider
from app.config.config import Settings
from app.ai_module.prompt_manager import PromptManager

GREETING = r"(?:hi+|hello+|hey+|hiya|yo|good (?:morning|afternoon|evening|night)|namaste|namaskar)"
ADDRESS = r"(?:bro|brother|sis|sister|bhai|bhaiya|dost|yaar|buddy|mate|sir|ma'am|edis|there)"
SMALL_TALK_SEPARATOR = r"[.!?, ]+"
SMALL_TALK = re.compile(
    rf"(?:{ADDRESS}{SMALL_TALK_SEPARATOR})?"
    rf"(?:{GREETING}(?:{SMALL_TALK_SEPARATOR}{ADDRESS})?{SMALL_TALK_SEPARATOR})*"
    rf"(?:{GREETING}|"
    r"how (?:are|r) (?:you|u)(?: doing)?(?: today)?|how(?: is|'s) it going|"
    r"how(?: is|'s) your day(?: going)?|what(?: is|'s) up|whats up|"
    r"what are you doing(?: right now)?|what you are doing|who are you|what are you|what is your name|"
    r"what(?: can| do) you do|what can you help (?:me |us )?with|"
    r"can you help me|tell me about yourself|what is edis|"
    r"how does edis work|(?:aap )?kaise (?:ho|hain)|kya haal hai|kya kar rahe ho|"
    r"thank you(?: so much)?|thanks(?: a lot)?|bye|goodbye)"
    rf"(?:{SMALL_TALK_SEPARATOR}{ADDRESS})?"
)


class DocumentChatService:
    def __init__(self, settings: Settings, models: ModelProvider):
        self.settings = settings
        self.models = models

    @staticmethod
    def is_small_talk(question: str) -> bool:
        normalized = " ".join(question.casefold().replace("\u2019", "'").split()).strip(" .!?,")
        return SMALL_TALK.fullmatch(normalized) is not None

    @staticmethod
    def is_unsupported_answer(answer: str) -> bool:
        normalized = answer.strip().casefold().replace("\u2019", "'").rstrip(".")
        return normalized in {
            "i don't know based on the documents",
            "i don't know based on the uploaded documents",
        }

    def general_reply(self, question: str, history: list[dict], documents: list[str]) -> str | None:
        if self.is_small_talk(question):
            return self.answer_directly(question)

        from langchain_core.exceptions import OutputParserException
        from langchain_core.output_parsers import JsonOutputParser

        recent = "\n".join(
            f"{turn['role']}: {turn['content'][:1_000]}"
            for turn in history[-6:]
        )
        chain = PromptManager.route_chat() | self.models.model | JsonOutputParser()
        result = chain.invoke({
            "question": question,
            "history": recent,
            "documents": "\n".join(documents),
        })
        if isinstance(result, dict):
            if result.get("intent") == "document":
                return None
            answer = result.get("answer")
            if result.get("intent") == "general" and isinstance(answer, str) and answer.strip():
                return answer.strip()
        raise OutputParserException("The model did not return a valid chat route.")

    def answer_directly(self, question: str) -> str:
        from langchain_core.output_parsers import StrOutputParser

        chain = PromptManager.direct_chat() | self.models.model | StrOutputParser()
        return chain.invoke({"question": question})

    def answer(self, question: str, hits: list[dict], history: list[dict]) -> str:
        if not hits:
            return "I don't know based on the uploaded documents."

        from langchain_core.messages import AIMessage, HumanMessage
        from langchain_core.output_parsers import StrOutputParser

        messages: list[Any] = []
        for item in history[-12:]:
            if item.get("role") == "user":
                messages.append(HumanMessage(content=item["content"]))
            elif item.get("role") == "assistant":
                messages.append(AIMessage(content=item["content"]))
        context = "\n\n".join(
            f"[Source: {hit['document']} page {hit['page']}]\n{hit['text']}"
            for hit in hits
        )[:20_000]
        prompt = PromptManager.document_chat()
        return (prompt | self.models.model | StrOutputParser()).invoke({
            "context": context,
            "history": messages,
            "question": question,
        })

    def rewrite_query(self, question: str, history: list[dict]) -> str:
        if not history:
            return question

        from langchain_core.messages import AIMessage, HumanMessage
        from langchain_core.output_parsers import StrOutputParser

        messages = [
            HumanMessage(content=item["content"])
            if item["role"] == "user"
            else AIMessage(content=item["content"])
            for item in history[-12:]
            if item["role"] in ("user", "assistant")
        ]
        prompt = PromptManager.rewrite_query()
        return (prompt | self.models.model | StrOutputParser()).invoke({
            "history": messages,
            "question": question,
        })
