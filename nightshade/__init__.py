import requests
import sys
import urllib


def get_movie_url(search):
    url = f"https://www.rottentomatoes.com/search?search={urllib.parse.quote(search)}"

    r = requests.get(url)
    if r.status_code != 200:
        raise RuntimeError("Bad request")

    return r.text


def test_cli():
    search = "terminator 2"
    if len(sys.argv) > 1:
        search = sys.argv[1]

    print(get_movie_url(search))
    return 0
