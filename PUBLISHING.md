# Publishing Site

Site consumes complete successful Integration artifacts. It does not check out providers,
update an adoption lock or run an Integration build. See the
[Integration design](https://github.com/TakashiSasaki/templates/blob/integration/docs/asynchronous-publication.md).

```sh
python -m pip install -r requirements-build.lock
python scripts/fetch_publication.py --output /tmp/templates-publication
python scripts/build_site.py --bundle /tmp/templates-publication --output /tmp/templates-build
```

Both output paths must be new. `fetch_publication.py --run RUN_ID` selects an earlier
retained successful publication; omit it to choose the newest available success.
No source edit or commit is required to change the input. Acquisition verifies the run,
artifact digest, archive boundaries and Bundle inventory. Corruption fails visibly;
failed or expired new publications do not hide older available successful artifacts.

`deploy-pages.yml` runs on Site pushes, successful publication completion or manual
dispatch. It checks out canonical Site code, builds with read-only permissions, and
passes the exact successful Pages artifact to a separate Pages-write job. A provider
or Integration failure never removes the current deployment. Pages environment settings
remain outside source control. Old PUBLICATION_* controller variables are unused.

GitHub schedules run only on the default branch. `refresh-publication.yml` therefore
hosts the timer and invokes the Integration-owned reusable publisher. It does not depend
on Site tests or deployment. Manual refresh recovers from a missed/disabled timer.

For visual development use the [local preview route](MAINTENANCE.md). A Site-only change
can use a previously downloaded Bundle for as long as its bytes remain available.
