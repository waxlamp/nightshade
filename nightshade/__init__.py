import click

from .tmdb import tmdb


@click.group()
def nightshade() -> None:
    """A command suite for interacting with Rotten Tomatoes."""
    pass


nightshade.add_command(tmdb)
