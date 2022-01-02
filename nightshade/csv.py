import csv as csvv
import click
import json
import sys
from typing import Optional

from .rottentomatoes import get_movies, get_movie_data, match_movie


def get_year(text: str) -> Optional[int]:
    value = None
    try:
        value = int(text)
    except ValueError:
        pass

    return value


@click.command()
@click.option("-i", "--input-file", type=click.Path(), required=True)
@click.option("-f", "--failure-file", type=click.Path(), required=True)
@click.option("-s", "--success-file", type=click.Path(), required=True)
@click.option("--skip", type=int, default=0)
def csv(input_file, failure_file, success_file, skip):
    # Open the failure file for appending.
    with open(failure_file, "a") as fail:
        writer = csvv.writer(fail)

        with open(success_file, "a") as success:
            # Open the CSV file.
            with open(input_file, newline="") as input_stream:
                reader = csvv.reader(input_stream)

                for i, row in enumerate(reader):
                    # Honor the skip parameter.
                    if i < skip:
                        continue

                    # Extract the title, year, and any notes.
                    title = row[0]
                    year = get_year(row[1])
                    url = row[2]
                    notes = row[3]

                    matches = None
                    year_text = "" if year is None else f" ({year})"
                    if url:
                        print(f"({i}) Retrieving data from {url} for '{title}{year_text}'...", end="", file=sys.stderr, flush=True)
                        movie = get_movie_data(url)
                        matches = [movie] if movie.title == title and (year is None or movie.year == year) else []
                        print("done", file=sys.stderr)
                    else:
                        # Perform a search for the title.
                        print(f"({i}) Searching for '{title}{year_text}'...", end="", file=sys.stderr, flush=True)
                        movies = get_movies(title)
                        matches = match_movie(movies, title, year)
                        print("done", file=sys.stderr)

                    # If there is only one hit, record it and move on.
                    if len(matches) == 1:
                        data = get_movie_data(matches[0].href).dict()
                        data["notes"] = notes
                        data["original"] = f"{title},{year or ''}"
                        print(json.dumps(data), file=success)
                    else:
                        writer.writerow(row)

                        if len(matches) == 0:
                            if url:
                                print(f"    {movie.title},{movie.year},{url},{notes}", file=fail)
                            else:
                                print("    (no matches found)", file=fail)
                        else:
                            for m in matches:
                                print(f"    {m.title},{m.year},{url},{notes}", file=fail)
