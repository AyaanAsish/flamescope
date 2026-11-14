"""`ScorerAgent`: a card plus excerpts to criterion scores with evidence

Contract: document 07 section 3.
"""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel

from flamescope_agents.base import Agent
from flamescope_common.schemas.agents import ScorerInput, ScorerOutput


class ScorerAgent(Agent):
    name: ClassVar[str] = "scorer"
    input_model: ClassVar[type[BaseModel]] = ScorerInput
    output_model: ClassVar[type[BaseModel] | None] = ScorerOutput
