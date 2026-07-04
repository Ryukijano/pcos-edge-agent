"""PCOS Context Schema — the structured object sent to every inference call."""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class BrowserContext:
    url: str = ""
    selection: str = ""
    tab_group: str = ""
    page_title: str = ""


@dataclass
class AndroidContext:
    calendar_summary: str = ""
    active_notifications: list = field(default_factory=list)
    battery_level: int = 100
    network_type: str = "wifi"  # wifi | cellular | offline


@dataclass
class WatchContext:
    heart_rate: Optional[int] = None
    activity_state: str = "idle"  # idle | walking | running | sleeping
    active_timer: Optional[str] = None
    voice_session_active: bool = False


@dataclass
class MemoryContext:
    recent_projects: list = field(default_factory=list)
    recent_papers: list = field(default_factory=list)
    todos: list = field(default_factory=list)
    recent_snippets: list = field(default_factory=list)


@dataclass
class PCOSContext:
    browser: BrowserContext = field(default_factory=BrowserContext)
    android: AndroidContext = field(default_factory=AndroidContext)
    watch: WatchContext = field(default_factory=WatchContext)
    memory: MemoryContext = field(default_factory=MemoryContext)

    def to_prompt_prefix(self) -> str:
        """Compress context into a prompt prefix for local models."""
        parts = []
        if self.browser.url:
            parts.append(f"[Browser: {self.browser.page_title} at {self.browser.url}]")
        if self.browser.selection:
            parts.append(f"[Selected text: {self.browser.selection[:300]}]")
        if self.memory.recent_projects:
            parts.append(f"[Recent projects: {', '.join(self.memory.recent_projects[:3])}]")
        if self.memory.recent_papers:
            parts.append(f"[Recent papers: {', '.join(self.memory.recent_papers[:3])}]")
        if self.android.active_notifications:
            parts.append(f"[Notifications: {len(self.android.active_notifications)} active]")
        if self.watch.activity_state != "idle":
            parts.append(f"[Watch: user is {self.watch.activity_state}]")
        return "\n".join(parts)
