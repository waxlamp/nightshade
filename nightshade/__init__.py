import click

from .search import search
from .tmdb import tmdb


@click.group()
def nightshade() -> None:
    """A command suite for interacting with Rotten Tomatoes."""
    pass


nightshade.add_command(search)
nightshade.add_command(tmdb)
