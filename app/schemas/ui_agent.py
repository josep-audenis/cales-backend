from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

ActionType = Literal["click", "toggle_on", "toggle_off", "select"]


class VisibleControl(BaseModel):
    target_id: str
    label: str
    type: str
    selected: bool | None = None
    disabled: bool | None = None
    metadata: dict[str, Any] | None = None


class UIAgentRequest(BaseModel):
    prompt: str
    page_id: str
    route: str
    material: str | None = None
    screen_state: dict[str, Any] = Field(default_factory=dict)
    visible_controls: list[VisibleControl] = Field(default_factory=list)


class UIAction(BaseModel):
    type: ActionType
    target_id: str
    reason: str
    value: Any | None = None


class UIAgentResponse(BaseModel):
    explanation: str
    actions: list[UIAction] = Field(default_factory=list)
    requires_confirmation: bool = False
