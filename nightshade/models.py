import pydantic
from typing import List, Optional


class MovieResult(pydantic.BaseModel):
    year: int
    title: str
    href: pydantic.HttpUrl


class MovieData(MovieResult):
    audience: Optional[int]
    tomatometer: Optional[int]
    rating: str
    genres: List[str]
    runtime: int
