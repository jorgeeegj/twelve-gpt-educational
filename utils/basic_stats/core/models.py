from pydantic import BaseModel, Field


class MetricResolution(BaseModel):
    """Output contract for the metric resolution tool call."""

    metric: str = Field(description="Exact column name to sort by")
    descending: bool = Field(
        description="True for most/highest/best, False for fewest/lowest/worst"
    )
    table: str = Field(description="'players' or 'teams'")


class QueryResult(BaseModel):
    """Structured result passed from execution to verbalization."""

    table: str
    metric: str
    rows: list[dict]
    filters_applied: dict

    is_tie: bool = False
    ranking_mode: str | None = None
    ranking_n: int | None = None
