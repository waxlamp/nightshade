from bs4 import BeautifulSoup
import nltk
import nltk.tokenize
import requests
import pydantic
import sys
import urllib


class MovieResult(pydantic.BaseModel):
    year: int
    title: str
    href: pydantic.HttpUrl


def is_subslice(subslice, full):
    if len(subslice) > len(full):
        return False

    return full[:len(subslice)] == subslice or is_subslice(subslice, full[1:])


def get_movies(search):
    url = f"https://www.rottentomatoes.com/search?search={urllib.parse.quote(search)}"

    r = requests.get(url)
    if r.status_code != 200:
        raise RuntimeError("Bad request")

    doc = BeautifulSoup(r.text, 'html.parser')
    slot = doc.find("search-page-result", attrs={"slot": "movie"})
    results = slot.find("ul").find_all("search-page-media-row")

    return [MovieResult(year=r.get("releaseyear"), title=r.find_all("a")[1].string.strip(), href=r.find_all("a")[1].get("href")) for r in results]


def get_movie_data(url):
    r = requests.get(url)
    if r.status_code != 200:
        raise RuntimeError("Bad request")

    doc = BeautifulSoup(r.text, "html.parser")

    scores = doc.find("score-board")
    title = scores.find("h1", attrs={"slot": "title"}).string
    info = scores.find("p", attrs={"slot": "info"})
    [year, genres, runtime] = info.text.split(", ")

    return {
        "audience": scores.get("audiencescore"),
        "tomatometer": scores.get("tomatometerscore"),
        "rating": scores.get("rating"),
        "genres": genres.split("/"),
        "runtime": runtime,
        "title": title,
        "year": year,
        "href": url,
    }


def match_movie(movies, name, year=None):
    def matches_exact(m):
        target = m.title.lower()
        search = name.lower()

        name_matches = search == target
        year_matches = year is None or year == m.year

        return name_matches and year_matches

    def matches_tokens(m):
        target = nltk.tokenize.word_tokenize(m.title.lower())
        search = nltk.tokenize.word_tokenize(name.lower())

        name_matches = is_subslice(search, target)
        year_matches = year is None or year == m.year

        return name_matches and year_matches

    def matches_fuzzy(m):
        target = m.title.lower()
        search = name.lower()

        name_matches = search in target
        year_matches = year is None or year == m.year

        return name_matches and year_matches

    exact = list(filter(matches_exact, movies))
    tokens = list(filter(matches_tokens, movies))
    fuzzy = list(filter(matches_fuzzy, movies))

    return exact or tokens or fuzzy


def test_cli():
    search = "terminator 2"
    if len(sys.argv) > 1:
        search = sys.argv[1]

    year = None
    if len(sys.argv) > 2:
        year = sys.argv[2]

    movies = get_movies(search)
    matches = match_movie(movies, search, year)

    if len(matches) == 1:
        data = get_movie_data(matches[0].href)
        print(data)

    return 0


def download_punkt():
    nltk.download("punkt")
