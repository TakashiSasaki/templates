"""Attach the Site audience shell to assembled shared services, without new identities."""
from __future__ import annotations
import html
import json
import re
from pathlib import Path


def prepare_services(site_root: Path, html_files: list[Path]) -> dict[str, object] | None:
    path = site_root / 'audience-runtime.json'
    if not path.is_file():
        return None  # Other callers can finalize minimal non-audience fixtures.
    model = json.loads(path.read_text())
    try:
        from scripts.finalize_site_metadata import is_inline_preview
    except ModuleNotFoundError:
        from finalize_site_metadata import is_inline_preview
    services = []
    for page in html_files:
        if is_inline_preview(page, site_root) or page.name == '404.html':
            continue
        relative = page.relative_to(site_root).as_posix()
        route = '/' + relative.removesuffix('index.html') if page.name == 'index.html' else '/' + relative
        if route not in model['routes']:
            services.append(route)
    model['services'] = sorted(services)
    return model


def attach_shell(source: str) -> str:
    """Static service pages use the same controller and presentation as document pages."""
    if re.search(r'<script\b[^>]*\bsrc=["\'][^"\']*javascripts/audience-context\.js["\']', source):
        return source
    def policy(match):
        directives = {}
        for item in html.unescape(match.group(1)).split(';'):
            words = item.split()
            if words:
                if words[0] in directives:
                    raise ValueError('duplicate shared-service CSP directive')
                directives[words[0]] = words[1:]
        for key in ('script-src', 'connect-src', 'style-src'):
            values = [v for v in directives.get(key, []) if v != "'none'"]
            if "'self'" not in values:
                values.append("'self'")
            directives[key] = values
        value = '; '.join(' '.join([key, *values]) for key, values in directives.items())
        return 'http-equiv="Content-Security-Policy" content="' + html.escape(value, quote=True) + '"'
    source = re.sub(r'http-equiv="Content-Security-Policy" content="([^"]*)"', policy, source)
    tags = '\n'.join([
        '<link rel="stylesheet" href="/stylesheets/extra.css">',
        '<script src="/javascripts/audience-context.js" defer></script>',
        '<script src="/javascripts/reader-navigation.js" defer></script>',
        '<script src="/javascripts/audience-shell.js" defer></script>',
    ])
    return source.replace('</head>', tags + '\n</head>', 1)


def finalize_presentation(site_root: Path, updates: dict[Path, str]) -> None:
    model = prepare_services(site_root, list(updates))
    if model is None:
        return
    try:
        from scripts.finalize_site_metadata import is_inline_preview
    except ModuleNotFoundError:
        from finalize_site_metadata import is_inline_preview
    for path, source in updates.items():
        if not is_inline_preview(path, site_root) and path.name != '404.html':
            updates[path] = attach_shell(source)
    (site_root / 'audience-runtime.json').write_text(
        json.dumps(model, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
