"""`ScenarioInterpreterAgent`: matches and coverage to a cited interpretation with caveats

Contract: document 07 section 3.
"""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel

from flamescope_agents.base import Agent
from flamescope_common.schemas.agents import ScenarioInterpreterInput, ScenarioInterpreterOutput


class ScenarioInterpreterAgent(Agent):
    name: ClassVar[str] = "scenario_interpreter"
    input_model: ClassVar[type[BaseModel]] = ScenarioInterpreterInput
    output_model: ClassVar[type[BaseModel] | None] = ScenarioInterpreterOutput
