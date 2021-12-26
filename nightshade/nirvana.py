import csv
import click
import json
import sys

from .rottentomatoes import get_movies, get_movie_data, match_movie


@click.command()
@click.option("-i", "--input-file", type=click.Path(), required=True)
@click.option("-f", "--failure-file", type=click.Path(), required=True)
def nirvana(input_file, failure_file):
    # Open the failure file for appending.
    with open(failure_file, "a") as fail:
        writer = csv.writer(fail)

        # Open the CSV file.
        with open(input_file, newline="") as input_stream:
            reader = csv.reader(input_stream)

            for row in reader:
                # Extract the title and any notes.
                title = title_text = row[5]
                notes = row[12]

                # Check for a year tagged onto the title.
                split = title_text.split(";")

                year = None
                try:
                    if len(split) > 1:
                        year = int(split[-1])
                        title = ";".join(split[:-1])
                except ValueError:
                    pass

                # Perform a search for the title.
                year_text = "" if year is None else f" ({year})"
                print(f"Searching for '{title}{year_text}'...", end="", file=sys.stderr, flush=True)
                movies = get_movies(title)
                matches = match_movie(movies, title, year)
                print("done", file=sys.stderr)

                # If there is only one hit, record it and move on.
                if len(matches) == 1:
                    data = get_movie_data(matches[0].href).dict()
                    data["notes"] = notes
                    print(json.dumps(data))
                else:
                    writer.writerow(row)

                    if len(matches) == 0:
                        print("    (no matches found)", file=fail)
                    else:
                        for m in matches:
                            print(f"    {m.title} ({m.year})", file=fail)
