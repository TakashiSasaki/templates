"""Public destination to static URL projection."""
from pathlib import Path, PurePosixPath

def public_path(destination: str) -> str:
    path = Path(destination)
    if path.name == "index.md":
        parent = path.parent.as_posix()
        return "/" if parent == "." else f"/{parent}/"
    return "/" + path.with_suffix("").as_posix() + "/"



def audience_routes(destinations):
    """The complete alias projection shared by audience producer and contract."""
    routes = {}
    for destination in destinations:
        dest = PurePosixPath(destination)
        aliases = [str(dest), '/' + str(dest)]
        if dest == PurePosixPath('index.md'):
            aliases += ['/', '', '/index.html', 'index.html']
        elif dest.name == 'index.md':
            aliases += [f'/{dest.parent}/', str(dest.parent), f'{dest.parent}/',
                        f'/{dest.parent}/index.html']
        elif dest.suffix == '.md':
            route = dest.parent / dest.stem
            aliases += [f'/{route}/', f'/{route}', f'/{route}.html']
        for alias in aliases:
            if alias in routes and routes[alias] != str(dest):
                raise ValueError('audience route collision: ' + alias)
            routes[alias] = str(dest)
    return routes
