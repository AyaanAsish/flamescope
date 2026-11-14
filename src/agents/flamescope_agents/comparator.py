"""`ComparatorAgent`: a diff matrix and facts to a short cited narrative

Contract: document 07 section 3.
"""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel

from flamescope_agents.base import Agent
from flamescope_common.schemas.agents import ComparatorInput, ComparatorOutput


class ComparatorAgent(Agent):
    name: ClassVar[str] = "comparator"
    input_model: ClassVar[type[BaseModel]] = ComparatorInput
    output_model: ClassVar[type[BaseModel] | None] = ComparatorOutput
