from __future__ import annotations

from datetime import datetime
import uuid

from pydantic import BaseModel, Field


class A2AMessage(BaseModel):
    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    thread_id: str
    task_id: str | None = None
    sender_agent_id: str
    recipient_agent_id: str
    subject: str
    body: str
    kind: str = "task_update"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class A2AThread(BaseModel):
    thread_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    topic: str
    participant_agent_ids: list[str] = Field(default_factory=list)
    messages: list[A2AMessage] = Field(default_factory=list)


class InMemoryA2ABus:
    def __init__(self) -> None:
        self._threads: dict[str, A2AThread] = {}

    def create_thread(
        self,
        session_id: str,
        topic: str,
        participant_agent_ids: list[str],
    ) -> A2AThread:
        thread = A2AThread(
            session_id=session_id,
            topic=topic,
            participant_agent_ids=participant_agent_ids,
        )
        self._threads[thread.thread_id] = thread
        return thread

    def send(self, message: A2AMessage) -> None:
        thread = self._threads.get(message.thread_id)
        if thread is None:
            raise KeyError(f"Unknown thread: {message.thread_id}")
        thread.messages.append(message)

    def threads_for_session(self, session_id: str) -> list[A2AThread]:
        return [
            thread for thread in self._threads.values() if thread.session_id == session_id
        ]
