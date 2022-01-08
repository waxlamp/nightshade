import click
import sys
from typing import Optional

from .rottentomatoes import get_movies, get_movie_data, match_movie


@click.command()
@click.option("-s", "--search-phrase", required=False)
@click.option("-y", "--year", required=False, type=int)
@click.option("-u", "--url", required=False)
def search(
    search_phrase: Optional[str], year: Optional[int], url: Optional[str]
) -> None:
    """
    Search Rotten Tomatoes for movie data.

    Either a SEARCH_PHRASE or URL must be supplied. Supplying SEARCH_PHRASE will
    cause nightshade to search Rotten Tomatoes and print out JSON records for
    search results. An optional YEAR will restrict the search to movies released
    in that year. If URL is supplied, it must be a Rotten Tomatoes movie page;
    nightshade will show a single search result for that movie. If YEAR and/or
    SEARCH_PHRASE is also supplied, nightshade will only show the result if the
    result's title and year also match the ones provided.
    """

    matches = []
    if search_phrase is None and url is None:
        print("At least one of SEARCH_PHRASE or URL must be specified", file=sys.stderr)
        sys.exit(1)
    elif search_phrase:
        # If there's a search phrase, run the search.
        movies = get_movies(search_phrase)
        matches = match_movie(movies, search_phrase, year)

        # If there's also a URL, then filter the search results by that URL (and
        # also the year, if specified).
        if url:
            matches = [
                m for m in matches if m.href == url and (year is None or m.year == year)
            ]
    elif url:
        # If there's only a URL, then collect that movie into the "search
        # results".
        matches = [get_movie_data(url)]

    # Print the matches.
    for movie in matches:
        data = get_movie_data(movie.href)
        print(data.json())
