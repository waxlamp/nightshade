import click
from typing import Optional

from .rottentomatoes import get_movies, get_movie_data, match_movie


@click.command()
@click.argument("search_phrase")
@click.argument("year", required=False, type=int)
def search(search_phrase: str, year: Optional[int]) -> None:
    """
    Search Rotten Tomatoes for movie data via SEARCH_PHRASE. An optional YEAR
    can be given to narrow the search.
    """

    movies = get_movies(search_phrase)
    matches = match_movie(movies, search_phrase, year)

    for movie in matches:
        data = get_movie_data(movie.href)
        print(data.json())
