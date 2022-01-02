from bs4 import BeautifulSoup
from bs4.element import Tag
import nltk.tokenize
import requests
import re
from typing import List, Optional
import urllib.parse

from .models import MovieData, MovieResult
from .util import is_subslice


def compute_minutes(runtime: str) -> Optional[int]:
    m = re.match(r"(?:(\d+)h )?(\d+)m", runtime)
    if m is None:
        return None

    hours = int(m.group(1)) if m.group(1) else 0
    minutes = int(m.group(2)) or 0

    return 60 * hours + minutes


def get_movies(search: str) -> List[MovieResult]:
    quoted_search = urllib.parse.quote(search)
    url = f"https://www.rottentomatoes.com/search?search={quoted_search}"

    r = requests.get(url)
    if r.status_code != 200:
        raise RuntimeError("Bad request")

    doc = BeautifulSoup(r.text, "html.parser")

    if not isinstance(
        slot := doc.find("search-page-result", attrs={"slot": "movie"}), Tag
    ):
        return []

    if not isinstance(ul := slot.find("ul"), Tag):
        raise RuntimeError("<ul> not found")

    results = ul.find_all("search-page-media-row")

    return [
        MovieResult(
            year=r.get("releaseyear") or None,
            title=r.find_all("a")[1].string.strip(),
            href=r.find_all("a")[1].get("href"),
        )
        for r in results
    ]


def get_movie_data(url: str) -> MovieData:
    r = requests.get(url)
    if r.status_code != 200:
        raise RuntimeError("Bad request")

    doc = BeautifulSoup(r.text, "html.parser")

    if not isinstance(scores := doc.find("score-board"), Tag):
        raise RuntimeError("<score-board> not found")

    if not isinstance(h1 := scores.find("h1", attrs={"slot": "title"}), Tag):
        raise RuntimeError("<h1> not found")
    title = h1.string

    if not isinstance(info := scores.find("p", attrs={"slot": "info"}), Tag):
        raise RuntimeError("<p> not found")

    # Analyze the info text.
    year_text = None
    genre_text = None
    runtime_text = None
    try:
        [year_text, genre_text, runtime_text] = info.text.split(", ")
    except ValueError:
        try:
            [genre_text, runtime_text] = info.text.split(", ")
        except ValueError:
            year_text = info.text

    year = int(year_text) if year_text is not None else None
    genres = genre_text.split("/") if genre_text is not None else []
    runtime = compute_minutes(runtime_text) if runtime_text is not None else None

    return MovieData(
        audience=scores.get("audiencescore") or None,
        tomatometer=scores.get("tomatometerscore") or None,
        rating=scores.get("rating"),
        genres=genres,
        runtime=runtime,
        title=title,
        year=year,
        href=url,
    )


def match_movie(
    movies: List[MovieResult], name: str, year: Optional[int] = None
) -> List[MovieResult]:
    def matches_exact(m: MovieResult) -> bool:
        target = m.title.lower()
        search = name.lower()

        name_matches = search == target
        year_matches = year is None or year == m.year

        return name_matches and year_matches

    def matches_tokens(m: MovieResult) -> bool:
        target = nltk.tokenize.word_tokenize(m.title.lower())
        search = nltk.tokenize.word_tokenize(name.lower())

        name_matches = is_subslice(search, target)
        year_matches = year is None or year == m.year

        return name_matches and year_matches

    def matches_fuzzy(m: MovieResult) -> bool:
        target = m.title.lower()
        search = name.lower()

        name_matches = search in target
        year_matches = year is None or year == m.year

        return name_matches and year_matches

    exact = list(filter(matches_exact, movies))
    tokens = list(filter(matches_tokens, movies))
    fuzzy = list(filter(matches_fuzzy, movies))

    return exact or tokens or fuzzy
