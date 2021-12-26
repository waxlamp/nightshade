# nightshade
Tools for retrieving movie data from Rotten Tomatoes

## Notes

To create a list of movies suitable for Nightshade from a NirvanaHQ export, use
the following command after exporting all data from Nirvana:

```bash
$ grep movielist nirvana.csv | mlr --csv --implicit-csv-header cat then cut -f 6,13 then put '$3 = $13; $13 = ""' | sed 's/\r/\\n/g' | tail -n +2 >movies.csv
```

Note that this requires adding a unique label to each movie item in Nirvana,
because the CSV export does not do a great job of identifying which project or
reference list a given item comes from. This example uses `movielist`.

The Miller command saying to extract fields 6 (title of the item) and 13 (the
body of the item), using the former as the search text to submit to Rotten
Tomatoes, and the latter as any page content that can be created in Notion for
the database row. The `put` section of the Miller pipeline "moves" the notes to
field three before leaving a blank in field two. This field will be used as the
(optional) release year to help Nightshade disambiguate between identically
named movies. The `sed` command handles dos-style carriage returns that Nirvana
embeds into item bodies, converting them to "escaped" unix-style newlines.
Finally, the `tail` command strips off the artifical header row the `mlr`
command inserts (which is necessary for proper handling of fields with embedded
commas).
