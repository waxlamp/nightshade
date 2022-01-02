import click
import nltk

from .notion import notion
from .csv import csv
from .search import search


@click.group()
def nightshade() -> None:
    """A command suite for interacting with Rotten Tomatoes."""
    pass


@click.command()
def prep() -> None:
    """
    Download tokenization models for use in `search` command.

    You will only need to run this subcommand at most one time (if the
    `nightshade search` command fails with an error about a missing NLTK
    model).
    """
    nltk.download("punkt")


nightshade.add_command(search)
nightshade.add_command(prep)
nightshade.add_command(notion)
nightshade.add_command(csv)
