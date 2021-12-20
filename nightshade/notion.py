import click
import os
import sys

from .models import MovieData


@click.command()
@click.option("-i", "--input", "input_file", type=click.Path())
@click.option("-c", "--credential-file", type=click.Path())
def notion(input_file: click.Path, credential_file: click.Path) -> None:
    """
    Create or update one or more rows in a Notion database.
    """

    # Check for Notion credentials.
    notion_key = os.getenv("NIGHTSHADE_NOTION_KEY")
    if credential_file:
        with open(credential_file) as f:
            notion_key = f.read().strip()

    if notion_key is None:
        print(
            "No credential file specified, and NIGHTSHADE_NOTION_KEY not set",
            file=sys.stderr,
        )
        sys.exit(1)

    # Open the input file for reading.
    input_stream = sys.stdin
    try:
        if input_file:
            input_stream = open(input_file)
    except OSError as err:
        print(f"error opening file '{input_file}': {err}", file=sys.stderr)
        sys.exit(1)

    # Create movie data models from the input.
    movies = (MovieData.parse_raw(line) for line in input_stream)

    print(list(movies))
