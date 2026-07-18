from dataclasses import dataclass, field
from typing import Optional
from enum import IntEnum

class EventPriority(IntEnum):
    NORMAL = 2

@dataclass(frozen=True, kw_only=True)
class EventPayload:
    timestamp: float = 123.0
    priority: EventPriority = EventPriority.NORMAL

@dataclass(frozen=True, kw_only=True)
class DictPayload(EventPayload):
    data: dict

p = DictPayload(data={"text": "hello"})
print(p.__dict__)
