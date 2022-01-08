import csv as csvv
import click
import json
import sys
import time
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
@click.option(
    "-i",
    "--input-file",
    type=click.Path(),
    required=True,
    help="CSV file containing movie search terms (see above)",
)
@click.option(
    "-f",
    "--failure-file",
    type=click.Path(),
    required=True,
    help="Failure records file (see above)",
)
@click.option(
    "-s",
    "--success-file",
    type=click.Path(),
    required=True,
    help="Success records file (see above)",
)
@click.option(
    "--skip",
    type=int,
    default=0,
    help="The number of input records to skip (default: 0)",
)
@click.option(
    "--force/--no-force",
    default=False,
    help="Overwrite failure and success files if they already exist",
)
@click.option(
    "--rate-limit",
    type=int,
    default=15,
    help="Number of seconds to pause between queries to Rotten Tomatoes (default: 15)",
)
def csv(
    input_file: str,
    failure_file: str,
    success_file: str,
    skip: bool,
    force: bool,
    rate_limit: int,
) -> None:
    """
    Bulk process movie titles, years, and/or Rotten Tomatoes URLs.

    INPUT_FILE should be a headerless CSV file with four columns, as follows:

    Column 1: title search phrase
    Column 2: release year
    Column 3: Rotten Tomatoes URL
    Column 4: Notes

    Within each row, at least one of Columns 1 and 3 MUST be non-empty (while
    columns 2 and 4 are always optional). If only Column 1 appears, nightshade
    will search Rotten Tomatoes for title match; if only one title is found, its
    full movie data, along with the title search phrase used, and any notes from
    column 4, will be emitted as a JSON line to the success file. If a year is
    also supplied, the search will be restricted only to movies of that release
    year (this can help with movies of the same title released in different
    years, such as remakes, or to prevent confusion between similarly
    named movies; try `nightshade search -s terminator` for an example of
    this).

    If Column 3 is supplied as a Rotten Tomatoes URL, nightshade will go
    directly to that page and retrieve the movie data there. If Columns 1 and/or
    2 are also supplied, nightshade will validate that the supplied title and/or
    release year match the data retrieved. If everything matches, the movie data
    is emitted to the success file.

    If the search turns up no results or more than one result, or if the Rotten
    Tomatoes URL data does not match the supplied title and/or year, then a
    record will be emitted to the failure file. The failure file is formatted as
    a modified CSV: each failure record is a block of lines, all but the first
    of which are indented. The first line of a block is a copy of the line from
    the input file that resulted in failure. If there are no matches, the next
    (indented) line will say so. If there were multiple matches, then a search
    line that will theoretically succeed in matching a specific movie will
    appear indented for each such search result. Finally, if the failure
    resulted from a non-validating Rotten Tomatoes URL, a line that would
    validate with that Rotten Tomatoes page appears indented (this is to help
    ensure that the URL you supply is exactly the movie you're expecting).

    You can convert the failure file into a new input file by editing the file
    block by block: look at the non-indented file that failed to find a single
    match; then look at the candidate lines in the indented block and either
    select one to replace the failing line, or edit the line directly to fix any
    errors, supply a year or URL, etc. Then invoke `nightshade` again with the
    new input file and repeat until the failure file is empty.
    """

    # Open the failure file for appending. Do it in "exclusive" mode (failing if
    # the file already exists) by default.
    mode = "w" if force else "x"
    try:
        with open(failure_file, mode) as fail, open(
            success_file, mode
        ) as success, open(input_file, newline="") as input_stream:
            # Open the CSV files.
            writer = csvv.writer(fail)
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
                    print(
                        f"({i}) Retrieving data from {url} for '{title}{year_text}'...",
                        end="",
                        file=sys.stderr,
                        flush=True,
                    )
                    movie = get_movie_data(url)
                    matches = (
                        [movie]
                        if movie.title == title and (year is None or movie.year == year)
                        else []
                    )
                    print("done", file=sys.stderr)
                else:
                    # Perform a search for the title.
                    print(
                        f"({i}) Searching for '{title}{year_text}'...",
                        end="",
                        file=sys.stderr,
                        flush=True,
                    )
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
                            print(
                                f"    {movie.title},{movie.year},{url},{notes}",
                                file=fail,
                            )
                        else:
                            print("    (no matches found)", file=fail)
                    else:
                        for m in matches:
                            print(
                                f"    {m.title},{m.year},{url},{notes}",
                                file=fail,
                            )

                # Pause to rate limit RT queries.
                time.sleep(rate_limit)
    except FileExistsError as e:
        print(f"error: {e}", file=sys.stderr)
