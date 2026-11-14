"""`EarthAppsAgent`: findings to candidate Earth applications (document 07 section 3)."""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel

from flamescope_agents.base import Agent
from flamescope_common.schemas.agents import EarthAppsInput, EarthAppsOutput


class EarthAppsAgent(Agent):
    name: ClassVar[str] = "earth_apps"
    input_model: ClassVar[type[BaseModel]] = EarthAppsInput
    output_model: ClassVar[type[BaseModel] | None] = EarthAppsOutput
