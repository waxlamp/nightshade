import click
import sys
from typing import Optional

from .rottentomatoes import get_movies, get_movie_data, match_movie


@click.command()
@click.option("-s", "--search-phrase", required=False)
@click.option("-y", "--year", required=False, type=int)
@click.option("-u", "--url", required=False)
def search(search_phrase: Optional[str], year: Optional[int], url: Optional[str]) -> None:
    """
    Search Rotten Tomatoes for movie data via SEARCH_PHRASE. An optional YEAR
    can be given to narrow the search.
    """

    if search_phrase is None and url is None:
        print("At least one of SEARCH_PHRASE or URL must be specified", file=sys.stderr)
        return 1

    matches = None
    if search_phrase:
        # If there's a search phrase, run the search.
        movies = get_movies(search_phrase)
        matches = match_movie(movies, search_phrase, year)

        # If there's also a URL, then filter the search results by that URL (and
        # also the year, if specified).
        if url:
            matches = [m for m in matches if m.href == url and (year is None or m.year == year)]
    else:
        # If there's only a URL, then collect that movie into the "search
        # results".
        matches = [get_movie_data(url)]

    # Print the matches.
    for movie in matches:
        data = get_movie_data(movie.href)
        print(data.json())
