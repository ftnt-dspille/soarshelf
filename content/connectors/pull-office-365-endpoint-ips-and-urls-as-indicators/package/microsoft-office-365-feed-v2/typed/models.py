"""Pydantic models: one input and one output model per operation.

OPERATION_MODELS maps each operation to its (input, output) models. Extra keys
are allowed on outputs so a feed field added later does not break playbooks.
"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field


class _Out(BaseModel):
    model_config = ConfigDict(extra="allow")


class FetchIndicatorIn(BaseModel):
    indicator_type: Literal["IPs", "URLs", "Both"] = "Both"
    last_pull_time: Optional[Union[int, float, str]] = None
    limit: Optional[int] = Field(default=None, ge=0)


class Indicator(_Out):
    value: str
    type: Literal["IP", "URL"]


class FetchIndicatorUpToDate(_Out):
    result: str
    up_to_date: bool
    region: str
    lastUpdated: Optional[str] = None


class FetchIndicatorOut(_Out):
    region: str
    lastUpdated: Optional[str] = None
    feedURL: Optional[str] = None
    indicators: List[Indicator]
    count: int
    up_to_date: bool


class ExecuteApiRequestIn(BaseModel):
    endpoint: str
    query: Optional[Dict[str, Any]] = None


class ExecuteApiRequestOut(_Out):
    status_code: int
    body: Any


OPERATION_MODELS = {
    "fetch_indicator": (FetchIndicatorIn, Union[FetchIndicatorOut, FetchIndicatorUpToDate]),
    "execute_api_request": (ExecuteApiRequestIn, ExecuteApiRequestOut),
}
