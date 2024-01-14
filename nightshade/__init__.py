import click

from .movie import movie


@click.group()
def nightshade() -> None:
    """A command suite for building movie, TV show, and book databases in Notion."""
    pass


nightshade.add_command(movie)
