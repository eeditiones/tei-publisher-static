from teipublisher.util import createDirectory, expandTemplateString, selectTemplate, expandTemplate, Config
import typer
from pathlib import Path
import json
import requests
from os import makedirs
from urllib.parse import quote_plus, urljoin, urlparse
from bs4 import BeautifulSoup

def fetch_document(config: Config, doc: str, params: dict = {}, target_path: str = None, clean: bool = True):
    """Recursively fetch a document.

    Args:
        config (Config): the global configuration object
        doc (str): relative path to the document
        params (dict, optional): additional parameters
        target_path (str, optional): path to the directory to be used for output
        clean (bool, optional): clear output directory before retrieving data
    """
    # retrieve metadata from server and merge it with passed in params
    meta = _loadMeta(config.baseUri, doc)
    if meta == None:
        return
    
    meta['doc'] = doc

    fetch(config, { **meta, **params }, target_path, clean)

def fetch(config: Config, meta: dict, target_path: str = None, clean: bool = True):
    """Recursively fetch a document using parameters given in `meta`. The relative path
    to the document should be specified in `meta["doc"]`.

    Args:
        config (Config): the global configuration object
        meta (dict): a dictionary of parameters to be used for the request
        params (dict, optional): additional parameters
        target_path (str, optional): path to the directory to be used for output
        clean (bool, optional): clear output directory before retrieving data
    """
    meta = { **meta, **config.variables }

    _checkCSS(meta, config.baseUri, config.baseDir)
    if target_path != None:
        output = createDirectory(config.baseDir, target_path, clean)
    else:
        output = createDirectory(config.baseDir, meta['doc'], clean)
    mapping = _loadMap(output)
    
    template = selectTemplate((meta.get('template'), 'view.html'))

    # try to load corresponding configuration by template, if any
    templateConfig = config.templates.get(template.name)
    if templateConfig == None:
        # fall back to either default or empty template
        templateConfig = config.templates.get('view.html') or { 'data': None }
    
    templateVars = meta
    if templateConfig.get('variables'):
        templateVars = { **meta, **templateConfig.get('variables') }

    expandTemplate(template, templateVars, output)

    dataConfigs = templateConfig['data']
    page = len(mapping)
    for view in dataConfigs:

        cfg = dataConfigs.get(view)
        if isinstance(cfg, str):
            path = Path(output, view)
            meta['doc'] = quote_plus(meta['doc'])
            uri = _load(config.baseUri, cfg, path, meta)
            mapping[uri] = view
        else:
            requestParams = {}
            if meta.get('odd'):
                requestParams['odd'] = meta.get('odd')
            if meta.get('view'): 
                requestParams['view'] = meta.get('view')
            if cfg != None:
                for key in cfg:
                    requestParams[key] = expandTemplateString(cfg[key], meta)

            typer.echo(f"Generating view '{typer.style(view, fg=typer.colors.GREEN)}' using template {template.name} and params {requestParams}..")
            uri = f"{config.baseUri}/api/parts/{quote_plus(meta['doc'])}/json"
            page += 1
            next = _retrieve(config, uri, requestParams, view, page, mapping, output)
            while next:
                page += 1
                next = _retrieve(config, uri, requestParams, view, page, mapping, output, next)
            typer.echo("\n")
    _save(output, mapping)

def _retrieve(config: Config, uri: str, reqParams: dict, view: str, page: int, mapping: dict, output: Path, root: dict = None):
    params = dict(reqParams)
    root and params.update(root)

    resp = requests.get(uri, params=params)
    if not resp.status_code == 200:
        print(resp.text)
        return
    data = resp.json()
    fileName = f"{view}-{page}.json"
    file = Path(output, fileName)
    
    typer.echo(f"\rWriting page: {typer.style(str(page), fg=typer.colors.BLUE)}", nl=False)

    content = _expandLinks(config, data['content'])

    with (open(file, 'w')) as f:
        data['content'] = str(content)
        json.dump(data, f, ensure_ascii=False, default=lambda x: x.toJSON())

    mapping[_getKey(params)] = fileName
    # if data was retrieved by id, also add a mapping for the corresponding root
    if root and root.get('id'):
        params.pop('id', None)
        params['root'] = data['root']
        mapping[_getKey(params)] = fileName
    _expandIds(content, mapping, params, fileName)

    if data.get('nextId'):
        return { 'id': data.get('nextId') }
    elif data.get('next'):
        return { 'root': data.get('next') }
    return None

def _load(baseUri: str, uriTemplate: str, output: Path, meta: dict):
    uri = expandTemplateString(uriTemplate, meta)
    typer.echo(f"Downloading {typer.style(uri, fg=typer.colors.GREEN)} to {output}")
    url = urljoin(baseUri, uri)
    resp = requests.get(url)
    with open(output, 'w', encoding="UTF-8") as f:
        resp.encoding = "UTF-8"
        f.write(resp.text)
    return uri

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
                makedirs(Path(baseDir, 'css'), exist_ok=True)
                with open(path, 'w') as f:
                    f.write(resp.text)
            else:
                typer.echo(typer.style(f"Stylesheet {file} not found", fg=typer.colors.CYAN))

def _expandIds(content: BeautifulSoup, mapping: dict, params: dict, fileName: str):
    """Parse the content for elements having an id and add mappings for those

    Args:
        content (BeautifulSoup): HTML tree
        mapping (dict): current mapping table
        params (dict): HTTP parameters used
        fileName (str): the output file to map entry to
    """
    idParams = dict(params)
    idParams.pop('root', None)
    
    elemWithId = content.select('[id]')
    for elem in elemWithId:
        idParams['id'] = elem['id']
        mapping[_getKey(idParams)] = fileName

def _expandLinks(config: Config, content: str) -> BeautifulSoup:
    """Parse the HTML content and transform relative links
    into links absolute to the defined context
    

    Args:
        config (Config): global configuration object
        content (str): HTML content as string

    Returns:
        BeautifulSoup: modified HTML tree
    """
    soup = BeautifulSoup(content, features='html.parser')
    links = soup.select('a[href]')
    for link in links:
        url = link['href']
        if urlparse(url).path:
            absolute = urljoin(config.baseUri, url)
            if absolute.startswith(config.baseUri):
                absolute = urljoin(config.context, url)
                link['href'] = absolute
    return soup

def _getKey(params: dict):
    encParams = []
    for key in sorted(params):
        encParams.append(f"{key}={params[key]}")
    return "&".join(encParams)    

def _save(output, mapping):
    mapFile = Path(output, 'index.json')
    with open(mapFile, 'w') as f:
        json.dump(mapping, f, ensure_ascii=False, indent=4)