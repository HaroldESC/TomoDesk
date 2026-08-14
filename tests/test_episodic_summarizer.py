import json

import pytest

from src.memory.episodic_summarizer import EpisodicSummarizer


class MockLLMProvider:
    def __init__(self, responses=None):
        self.responses = responses or []
        self.call_count = 0
        self.last_messages = None

    def generate(self, messages):
        self.last_messages = messages
        if self.call_count < len(self.responses):
            response = self.responses[self.call_count]
            self.call_count += 1
            return response
        return "[]"


class MockMemoryManager:
    def __init__(self, messages=None):
        self.messages = messages or []
        self.episodic_memories = []
        self.episodic_log = []

    def get_recent_messages(self, n=None):
        if n:
            return self.messages[-n:]
        return self.messages

    def add_episodic_memory(self, summary, importance_score, source):
        self.episodic_memories.append({
            "summary": summary,
            "importance_score": importance_score,
            "source": source,
        })
        self.episodic_log.append({
            "summary": summary,
            "importance_score": importance_score,
            "source": source,
            "id": len(self.episodic_log) + 1,
            "timestamp": "2026-06-08T00:00:00",
        })
        return f"episodic_{len(self.episodic_memories)}"

    def list_episodic_log(self):
        return self.episodic_log


def test_should_check_triggers_at_threshold():
    mm = MockMemoryManager()
    config = {"memory": {"episodic_message_threshold": 15, "episodic_auto_threshold": 0.6}}
    summarizer = EpisodicSummarizer(mm, None, config)

    mm.messages = [{"role": "user", "content": f"msg {i}"} for i in range(10)]
    assert not summarizer.should_check()

    mm.messages = [{"role": "user", "content": f"msg {i}"} for i in range(16)]
    assert summarizer.should_check()

    mm.messages = [{"role": "user", "content": f"msg {i}"} for i in range(20)]
    assert not summarizer.should_check()


def test_summarize_conversation_empty():
    mm = MockMemoryManager()
    mm.messages = [{"role": "user", "content": f"msg {i}"} for i in range(5)]
    config = {"memory": {"episodic_message_threshold": 15, "episodic_auto_threshold": 0.6}}
    summarizer = EpisodicSummarizer(mm, MockLLMProvider(), config)

    results = summarizer.summarize_conversation()
    assert results == []


def test_summarize_conversation_with_results():
    mm = MockMemoryManager()
    mm.messages = [
        {"role": "user", "content": f"msg {i}"} for i in range(30)
    ]

    llm_response = json.dumps([
        {"summary": "User started project TomoDesk", "importance_score": 0.9},
        {"summary": "User prefers coffee in the morning", "importance_score": 0.55},
    ])

    config = {"memory": {"episodic_message_threshold": 15, "episodic_auto_threshold": 0.6}}
    summarizer = EpisodicSummarizer(mm, MockLLMProvider([llm_response]), config)

    results = summarizer.summarize_conversation()

    assert len(results) == 2
    assert results[0]["stored"] is True
    assert results[1]["stored"] is False

    assert len(mm.episodic_memories) == 1
    assert mm.episodic_memories[0]["summary"] == "User started project TomoDesk"
    assert mm.episodic_memories[0]["source"] == "auto"


def test_parse_summarization_response_valid():
    config = {"memory": {"episodic_message_threshold": 15, "episodic_auto_threshold": 0.6}}
    summarizer = EpisodicSummarizer(MockMemoryManager(), None, config)

    response = json.dumps([
        {"summary": "Event one", "importance_score": 0.8},
        {"summary": "Event two", "importance_score": 0.3},
    ])

    results = summarizer._parse_summarization_response(response)
    assert len(results) == 2
    assert results[0]["summary"] == "Event one"
    assert results[0]["importance_score"] == 0.8


def test_parse_summarization_response_invalid():
    config = {"memory": {"episodic_message_threshold": 15, "episodic_auto_threshold": 0.6}}
    summarizer = EpisodicSummarizer(MockMemoryManager(), None, config)

    results = summarizer._parse_summarization_response("Not JSON at all")
    assert results == []


def test_parse_summarization_response_markdown():
    config = {"memory": {"episodic_message_threshold": 15, "episodic_auto_threshold": 0.6}}
    summarizer = EpisodicSummarizer(MockMemoryManager(), None, config)

    response = '```json\n[{"summary": "Test", "importance_score": 0.7}]\n```'
    results = summarizer._parse_summarization_response(response)
    assert len(results) == 1
    assert results[0]["summary"] == "Test"


def test_parse_summarization_response_empty():
    config = {"memory": {"episodic_message_threshold": 15, "episodic_auto_threshold": 0.6}}
    summarizer = EpisodicSummarizer(MockMemoryManager(), None, config)

    results = summarizer._parse_summarization_response("[]")
    assert results == []


def test_summarize_on_session_end():
    mm = MockMemoryManager()
    mm.messages = [
        {"role": "user", "content": f"Session msg {i}"} for i in range(20)
    ]

    llm_response = json.dumps([
        {"summary": "Session summary test", "importance_score": 0.75},
    ])

    config = {"memory": {"episodic_message_threshold": 15, "episodic_auto_threshold": 0.6}}
    summarizer = EpisodicSummarizer(mm, MockLLMProvider([llm_response]), config)

    results = summarizer.summarize_on_session_end()
    assert len(results) == 1
    assert results[0]["stored"] is True
