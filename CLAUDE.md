# uk-food-data: Development Guidelines

- Public repo `shakethatweight/uk-food-data`. Holds ONLY the build script, docs and licences. The data file is published as GitHub Release assets and must never be committed (`.gitignore` blocks `*.csv*`).
- Never put anything private here: no internal hostnames, server paths, emails other than the generic dev@ in the User-Agent.
- `bin/build-off-uk.py`: streams the Open Food Facts CSV export (tab-separated, gzip) and writes `off-uk-YYYY-MM-DD.csv.gz` + `stats.json`. Python stdlib only (must run on 3.9). Column list, filters and number formats (kcal integer, salt 2 dp, other grams 1 dp) are a contract shared with the WordPress importer and live-lookup mapper (stw-myjurnee-food `STW_MJ_Food_Off::product_to_row()`) - change them together and bump the README.
- `bin/publish.sh`: runs the build memory-capped via `systemd-run --user`, refuses to publish under 100k rows, creates release tag `YYYY-MM-DD` (Europe/London), prunes to the newest 8.
- Export quirks: no `product_name_en` or `nutrition_data_per` columns; `unit` is inferred from `quantity`. Export URL redirects to S3; send the custom User-Agent.
- Work dir (downloads, output) is outside the repo at `/var/www/shared/uk-food-data-work/`; the repo checkout lives alongside it.
- Memory: never run the build uncapped on the dev box (see publish.sh for the systemd-run flags).
- Licences: data ODbL 1.0 / DbCL, script MIT. Keep the attribution line in README and release notes.
- Every change: bump the version in `VERSION`, update README/CLAUDE.md, commit via `stw_commit`.
