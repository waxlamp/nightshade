import pydantic
from typing import List, Optional


class TMDBSearchResult(pydantic.BaseModel):
    id: int
    title: str
    release_date: str
    overview: str


class TMDBMovie(pydantic.BaseModel):
    id: int
    genres: List[str]
    overview: str
    release_date: str
    runtime: int
    title: str
    mpaa_rating: Optional[str]
    vote_average: float
    vote_count: int
