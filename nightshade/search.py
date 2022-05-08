import click
import json
import sys
from typing import Optional

from .rottentomatoes import get_movies, get_movie_data, match_movie
from .models import MovieData


def display(m: MovieData) -> str:
    return f"""{m.title} ({m.year}) - {m.href}
        Genres: {", ".join(m.genres)}
        MPAA rating: {m.rating}
        Audience score: {m.audience}
        Tomatometer score: {m.tomatometer}
        Runtime: {m.runtime} minutes"""


def process_matches(matches, notes, search_phrase, instream):
    # Exit early if there were no results.
    if not matches:
        print("No movies matched.", file=sys.stderr)
        return

    # Print the matches and store the canonicalized data in an array.
    selections = []
    for index, movie in enumerate(matches):
        data = get_movie_data(movie.href)
        print(f"({index + 1}) {display(data)}", file=sys.stderr)

        datadict = data.dict()
        datadict["notes"] = notes
        datadict["original"] = search_phrase or ""

        selections.append(datadict)

    # Ask the user to confirm which entry is the one to use.
    which = -1
    while not 0 <= which < len(matches):
        print("Which entry ('s' to skip; enter to select the first one)? ", end="", flush=True, file=sys.stderr)
        text = instream.readline().strip()
        if text == "s":
            return
        elif text == "":
            text = "1"

        try:
            which = int(text) - 1
        except ValueError:
            continue

    print(json.dumps(selections[which]))


@click.command()
@click.option("-s", "--search-phrase", required=False)
@click.option("-y", "--year", required=False, type=int)
@click.option("-u", "--url", required=False)
@click.option("-n", "--notes", default="")
def search(
    search_phrase: Optional[str], year: Optional[int], url: Optional[str], notes: str
) -> None:
    """
    Search Rotten Tomatoes for movie data.

    Either a SEARCH_PHRASE or URL must be supplied. Supplying SEARCH_PHRASE will
    cause nightshade to search Rotten Tomatoes and print out JSON records for
    search results. An optional YEAR will restrict the search to movies released
    in that year. If URL is supplied, it must be a Rotten Tomatoes movie page;
    nightshade will show a single search result for that movie. If YEAR and/or
    SEARCH_PHRASE is also supplied, nightshade will only show the result if the
    result's title and year also match the ones provided. An optional NOTES will
    append that content to the Notion entry (if the output is passed to
    `nightshade notion`).
    """

    matches = []
    if search_phrase is None and url is None:
        # Attempt to open the TTY.
        try:
            tty = open("/dev/tty")
        except OSError:
            tty = os.fdopen(2)

        spacer = ""
        for inputline in (x.strip() for x in sys.stdin):
            print(f"{spacer}processing search string '{inputline}'...", file=sys.stderr)
            spacer = "\n"

            components = inputline.split(";")
            search_phrase = components[0]
            try:
                year = int(components[1]) if len(components) > 1 else None
            except ValueError:
                print(f"error: value '{components[1]}' for year much be an integer", file=sys.stderr)
                continue

            url = components[2] if len(components) > 2 else None

            movies = get_movies(search_phrase)
            matches = match_movie(movies, search_phrase, year)

            if url:
                matches = [
                    m for m in matches if m.href == url and (year is None or m.year == year)
                ]

            process_matches(matches, notes, search_phrase or url, tty)

        sys.exit(0)
    elif search_phrase:
        # If there's a search phrase, run the search.
        movies = get_movies(search_phrase)
        matches = match_movie(movies, search_phrase, year)

        # If there's also a URL, then filter the search results by that URL (and
        # also the year, if specified).
        if url:
            matches = [
                m for m in matches if m.href == url and (year is None or m.year == year)
            ]
    elif url:
        # If there's only a URL, then collect that movie into the "search
        # results".
        matches = [get_movie_data(url)]

    process_matches(matches, notes, search_phrase or url, sys.stdin)
