"""`ExtractorAgent`: parsed document sections to an investigation card draft

Contract: document 07 section 3.
"""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel

from flamescope_agents.base import Agent
from flamescope_common.schemas.agents import ExtractorInput, ExtractorOutput


class ExtractorAgent(Agent):
    name: ClassVar[str] = "extractor"
    input_model: ClassVar[type[BaseModel]] = ExtractorInput
    output_model: ClassVar[type[BaseModel] | None] = ExtractorOutput
