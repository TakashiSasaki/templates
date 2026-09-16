# Publication staging

This responsibility belongs to the independent Integration authority. Site consumes
only the reviewed release selected in `integration-source.json`.

Provider candidates qualify with Integration without Site rendering or deployment.
Integration may stage mappings and explicitly promote exact merged provider commits;
a qualified candidate does not itself constitute a reviewed release or Site adoption.
See the [Integration authority](https://github.com/TakashiSasaki/templates/tree/integration)
and its [release contract](https://github.com/TakashiSasaki/templates/blob/integration/RELEASE.md). Site uses [PUBLISHING.md](PUBLISHING.md)
for explicit adoption, consumer qualification and deployment.

Site runtime/deployed-document freshness remains a separate Site responsibility.
