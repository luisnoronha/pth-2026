"""Rex's final answer, returned as structured output."""

from pydantic import BaseModel, Field


class Briefing(BaseModel):
    """A short briefing for the analyst about one company."""

    company: str = Field(description="The company the briefing is about.")
    lines: list[str] = Field(description="Up to 5 short lines with the key facts.", max_length=5)
    sources: list[str] = Field(default_factory=list, description="Links that back the facts.")
