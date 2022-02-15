from teipublisher.util import createDirectory, expandTemplateString, expandTemplate, Config
import typer
from pathlib import Path
import json
import requests
from urllib.parse import quote_plus

def fetch(config: Config, doc: str, clear: bool = False):
    typer.echo(f"Processing {typer.style(doc, typer.colors.MAGENTA)}...")
    # retrieve metadata from server and merge it with passed in params
    meta = _loadMeta(config.baseUri, doc)
    if meta == None:
        return
    
    meta['doc'] = quote_plus(doc)
    meta = { **meta, **config.variables }

    _checkCSS(meta, config.baseUri, config.baseDir)
    output = createDirectory(config.baseDir, doc, clear)
    mapping = _loadMap(output)
    
    template = expandTemplate((meta.get('template'), 'view.html'), meta, output)
    typer.echo(f"Fetching {meta['doc']} using template {template}, ODD {meta.get('odd')} and view {meta.get('view')} ...")

    requestConfigs = config.templates.get(template) or { 'main': None }

    page = len(mapping)
    for view in requestConfigs:
        typer.echo(f"Generating view '{typer.style(view, fg=typer.colors.GREEN)}'...")

        cfg = requestConfigs.get(view)
        if isinstance(cfg, str):
            path = Path(output, view)
            _load(cfg, path, meta)
            mapping[cfg] = view
        else:
            requestParams = {
                'odd': meta['odd'],
                'view': meta['view']
            }
            if cfg != None:
                requestParams.update(cfg)

            uri = f"{config.baseUri}/api/parts/{quote_plus(doc)}/json"

            page += 1
            next = _retrieve(uri, requestParams, view, page, mapping, output)
            while next:
                page += 1
                next = _retrieve(uri, requestParams, view, page, mapping, output, next)
            typer.echo("\n")
    _save(output, mapping)

def _retrieve(uri: str, params: dict, view: str, page: int, mapping: dict, output: Path, root: str = None):
    if root:
        params['root'] = root

    resp = requests.get(uri, params=params)
    data = resp.json()
    fileName = f"{view}-{page}.json"
    file = Path(output, fileName)
    typer.echo(f"\rWriting page: {typer.style(str(page), fg=typer.colors.BLUE)}", nl=False)
    with (open(file, 'w')) as f:
        json.dump(data, f, ensure_ascii=False, default=lambda x: x.toJSON())

    mapping[_getKey(params)] = fileName

    return data.get('next')

def _load(uriTemplate: str, output: Path, meta: dict):
    uri = expandTemplateString(uriTemplate, meta)
    typer.echo(f"Downloading {typer.style(uri, fg=typer.colors.MAGENTA)} to {output}")
    resp = requests.get(uri)
    with open(output, 'w') as f:
        f.write(resp.text)

def _loadMap(output: Path):
    indexPath = Path(output, 'index.json')
    if indexPath.exists():
        with open(indexPath, 'r') as f:
            return json.load(f)
    return {}

def _loadMeta(baseUri, doc) -> dict:
    resp = requests.get(f"{baseUri}/api/document/{quote_plus(doc)}/meta")
    if resp.status_code != 200:
        typer.echo(typer.style(f"Skipping document: {doc}!", fg=typer.colors.RED))
        return None
    return resp.json()

def _checkCSS(meta: dict, baseUri: str, baseDir: Path):
    if meta.get('odd'):
        file = f"{meta['odd'][:-4]}.css"
        path = Path(baseDir, 'css', file)
        if not path.exists():
            resp = requests.get(f"{baseUri}/transform/{file}")
            if resp.status_code == 200:
                typer.echo(f"Copying {file} to {path}.")
                with open(path, 'w') as f:
                    f.write(resp.text)
            else:
                typer.echo(typer.style(f"Stylesheet {file} not found", fg=typer.colors.CYAN))
    else:
        print('No ODD found')

def _getKey(params: dict):
    encParams = []
    for key in sorted(params):
        encParams.append(f"{key}={params[key]}")
    return "&".join(encParams)    

def _save(output, mapping):
    mapFile = Path(output, 'index.json')
    with open(mapFile, 'w') as f:
        json.dump(mapping, f, ensure_ascii=False, indent=4)