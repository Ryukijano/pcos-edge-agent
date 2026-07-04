"""PCOS Context Schema — structured objects for every inference call.

Pydantic v2 models for the five context planes and the task object.
These are the canonical types used across the entire broker pipeline.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Modality(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"


class Sensitivity(str, Enum):
    PRIVATE = "private"
    NORMAL = "normal"


class TaskType(str, Enum):
    TRANSFORM = "transform"
    ACTION = "action"
    REASONING = "reasoning"
    RETRIEVAL = "retrieval"


class NetworkType(str, Enum):
    WIFI = "wifi"
    CELLULAR = "cellular"
    OFFLINE = "offline"


# ── Context planes ──────────────────────────────────────────────

class BrowserContext(BaseModel):
    url: str = ""
    selection: str = ""
    tab_group: str = ""
    page_title: str = ""
    dom_summary: str = ""           # compressed DOM text for grounding
    favicons: list[str] = Field(default_factory=list)


class AndroidContext(BaseModel):
    calendar_summary: str = ""
    active_notifications: list[dict] = Field(default_factory=list)
    battery_level: int = 100
    network_type: NetworkType = NetworkType.WIFI
    is_charging: bool = False
    sensor_snapshot: dict = Field(default_factory=dict)  # accel, gyro, etc.


class WatchContext(BaseModel):
    heart_rate: Optional[int] = None
    activity_state: str = "idle"   # idle | walking | running | sleeping
    active_timer: Optional[str] = None
    voice_session_active: bool = False
    on_wrist: bool = True
    broker_status: str = "unknown"  # ok | degraded | offline | unknown
    stress_level: Optional[str] = None  # low | moderate | high (derived from HR + activity)


class MemoryContext(BaseModel):
    recent_projects: list[str] = Field(default_factory=list)
    recent_papers: list[str] = Field(default_factory=list)
    todos: list[str] = Field(default_factory=list)
    recent_snippets: list[str] = Field(default_factory=list)
    piecesos_hits: list[dict] = Field(default_factory=list)  # raw LTM results


class CalendarContext(BaseModel):
    next_event_title: str = ""
    next_event_time: str = ""
    is_in_meeting: bool = False


class FileContext(BaseModel):
    recent_files: list[str] = Field(default_factory=list)
    git_branch: str = ""
    git_status: str = ""


class DesktopContext(BaseModel):
    """Desktop environment context — local LiteRT-LM server, GPU availability."""
    litert_server_available: bool = False
    litert_server_url: str = "http://localhost:9379"
    has_gpu: bool = False
    gpu_name: str = ""
    os_type: str = ""  # linux | macos | windows


class PCOSContext(BaseModel):
    """Full context object assembled before routing."""
    browser: BrowserContext = Field(default_factory=BrowserContext)
    android: AndroidContext = Field(default_factory=AndroidContext)
    watch: WatchContext = Field(default_factory=WatchContext)
    memory: MemoryContext = Field(default_factory=MemoryContext)
    calendar: CalendarContext = Field(default_factory=CalendarContext)
    files: FileContext = Field(default_factory=FileContext)
    desktop: DesktopContext = Field(default_factory=DesktopContext)

    def to_prompt_prefix(self, max_chars: int = 1200) -> str:
        """Compress context into a prompt prefix for local models.

        Truncates to *max_chars* to stay within local model context windows.
        """
        parts: list[str] = []
        if self.browser.url:
            parts.append(f"[Browser: {self.browser.page_title} at {self.browser.url}]")
        if self.browser.selection:
            parts.append(f"[Selected: {self.browser.selection[:300]}]")
        if self.browser.dom_summary:
            parts.append(f"[Page context: {self.browser.dom_summary[:200]}]")
        if self.memory.recent_projects:
            parts.append(f"[Recent projects: {', '.join(self.memory.recent_projects[:3])}]")
        if self.memory.recent_papers:
            parts.append(f"[Recent papers: {', '.join(self.memory.recent_papers[:3])}]")
        if self.memory.todos:
            parts.append(f"[Todos: {'; '.join(self.memory.todos[:3])}]")
        if self.memory.piecesos_hits:
            top = self.memory.piecesos_hits[:2]
            parts.append(f"[LTM: {top}]")
        if self.android.active_notifications:
            parts.append(f"[Notifications: {len(self.android.active_notifications)} active]")
        if self.android.network_type == NetworkType.OFFLINE:
            parts.append("[Network: offline]")
        if self.watch.activity_state != "idle":
            parts.append(f"[Watch: user is {self.watch.activity_state}]")
        if self.calendar.is_in_meeting:
            parts.append(f"[In meeting: {self.calendar.next_event_title}]")
        if self.files.git_branch:
            parts.append(f"[Git: {self.files.git_branch}]")
        result = "\n".join(parts)
        return result[:max_chars] if len(result) > max_chars else result

    def is_offline(self) -> bool:
        return self.android.network_type == NetworkType.OFFLINE


# ── Task object ─────────────────────────────────────────────────

class TaskObject(BaseModel):
    """The incoming task to be routed and executed."""
    text: str
    modality: Modality = Modality.TEXT
    sensitivity: Sensitivity = Sensitivity.NORMAL
    task_type: TaskType = TaskType.TRANSFORM
    is_short: bool = True            # under ~500 tokens
    is_webpage_grounded: bool = False
    requires_personal_context: bool = False
    requires_action: bool = False
    exceeds_local_limits: bool = False
    confidence_threshold: float = 0.7
    user_explicit_escalate: bool = False

    def is_private(self) -> bool:
        return self.sensitivity == Sensitivity.PRIVATE
