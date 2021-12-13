from bs4 import BeautifulSoup
import requests
import sys
import urllib


def get_movies(search):
    url = f"https://www.rottentomatoes.com/search?search={urllib.parse.quote(search)}"

    r = requests.get(url)
    if r.status_code != 200:
        raise RuntimeError("Bad request")

    doc = BeautifulSoup(r.text, 'html.parser')
    slot = doc.find("search-page-result", attrs={"slot": "movie"})
    results = slot.find("ul").find_all("search-page-media-row")

    return [{"year": r.get("releaseyear"),
             "name": r.find_all("a")[1].string.strip(),
             "href": r.find_all("a")[1].get("href")}
            for r in results]


def match_movie(movies, name, year=None):
    def matches_exact(m):
        target = m["name"].lower()
        search = name.lower()

        name_matches = search == target
        year_matches = year is None or year == m["year"]

        return name_matches and year_matches

    def matches_fuzzy(m):
        target = m["name"].lower()
        search = name.lower()

        name_matches = search in target
        year_matches = year is None or year == m["year"]

        return name_matches and year_matches

    return list(filter(matches_exact, movies)) or list(filter(matches_fuzzy, movies))


def test_cli():
    search = "terminator 2"
    if len(sys.argv) > 1:
        search = sys.argv[1]

    year = None
    if len(sys.argv) > 2:
        year = sys.argv[2]

    movies = get_movies(search)
    print(match_movie(movies, search, year))

    return 0
