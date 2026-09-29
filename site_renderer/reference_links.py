"""Keep reference translations usable when canonical headings have moved.

Only the staged presentation is adjusted. Source text and review evidence remain
unchanged; canonical links still pass the normal strict publication checks.
"""
from html.parser import HTMLParser
from pathlib import PurePosixPath
import posixpath
from urllib.parse import unquote, urlsplit, urlunsplit

from markdown import markdown

from publication_bundle.markdown import _rewrite_markdown
from publication_bundle.paths import audience_routes, public_path


class Anchors(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get('id'):
            self.ids.add(attrs['id'])
        if tag == 'a' and attrs.get('name'):
            self.ids.add(attrs['name'])


def repair_reference_fragments(docs, translations):
    documents = {p.relative_to(docs).as_posix(): p for p in docs.rglob('*.md')}
    aliases = audience_routes(documents)
    anchors = {}
    repairs = 0

    def ids(destination):
        if destination not in anchors:
            parser = Anchors()
            parser.feed(markdown(documents[destination].read_text(encoding='utf-8'),
                                 extensions=['toc', 'attr_list', 'fenced_code', 'md_in_html']))
            anchors[destination] = parser.ids
        return anchors[destination]

    for translation in translations['translations']:
        relative = translation['translation_destination']
        path = documents[relative]

        def rewrite(url):
            parsed = urlsplit(url)
            if parsed.scheme or parsed.netloc or not parsed.fragment:
                return url
            target = unquote(parsed.path)
            if not target:
                destination = relative
            elif target.startswith('/'):
                destination = aliases.get(target)
            else:
                destination = aliases.get(posixpath.normpath(
                    posixpath.join(posixpath.dirname(relative), target)))
            if destination is None or unquote(parsed.fragment) in ids(destination):
                return url
            # A removed section still has a useful page. An empty in-page link
            # must become an explicit page URL, rather than an empty href.
            return urlunsplit(('', '', parsed.path or public_path(relative), parsed.query, ''))

        text, count = _rewrite_markdown(path.read_text(encoding='utf-8'),
            source_document=PurePosixPath(relative), site_document=PurePosixPath(relative),
            document_targets={}, asset_rules=[], docs_root=docs,
            publication='reference-translations', site_source_paths=None,
            absolute_url_rewriter=rewrite)
        if count:
            path.write_text(text, encoding='utf-8')
            repairs += count
    return repairs
