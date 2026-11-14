"""`InsightQAAgent`: a question plus retrieved context to a streamed, cited plain-text answer

Contract: document 07 section 3.
"""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel

from flamescope_agents.base import Agent
from flamescope_common.schemas.agents import InsightQAInput


class InsightQAAgent(Agent):
    name: ClassVar[str] = "insight_qa"
    input_model: ClassVar[type[BaseModel]] = InsightQAInput
    output_model: ClassVar[type[BaseModel] | None] = None
