import click

from .tmdb import tmdb


@click.group()
def nightshade() -> None:
    """A command suite for interacting with TMDB and Notion databases."""
    pass


nightshade.add_command(tmdb)
