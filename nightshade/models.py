import pydantic
from typing import List, Optional


class MovieResult(pydantic.BaseModel):
    year: Optional[int]
    title: str
    href: pydantic.HttpUrl


class MovieData(MovieResult):
    audience: Optional[int]
    tomatometer: Optional[int]
    rating: Optional[str]
    genres: List[str]
    runtime: Optional[int]
