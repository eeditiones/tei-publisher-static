from tpgen.util import createDirectory, expandTemplateString, selectTemplate, expandTemplate, Config
import typer
from pathlib import Path
import json
import requests
from os import makedirs
from urllib.parse import quote_plus, urljoin, urlparse
from bs4 import BeautifulSoup, Tag

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
    config.verbose and typer.echo(f"\nProcessing {typer.style(meta.get('doc'), typer.colors.BLUE)}...")
    meta = { **meta, **config.variables }

    _checkCSS(meta, config)
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
            uri = _load(config, cfg, path, meta)
            mapping[uri] = view
        else:
            requestParams = {}
            if meta.get('odd'):
                requestParams['odd'] = meta.get('odd')
            if meta.get('view'): 
                requestParams['view'] = meta.get('view')
            index = None
            if cfg != None:
                for key in cfg:
                    if key != 'index':
                        requestParams[key] = expandTemplateString(cfg[key], meta) if isinstance(cfg[key], str) else cfg[key]
                index = cfg.get('index')
            if config.verbose:
                typer.echo(f"Generating view '{typer.style(view, fg=typer.colors.GREEN)}' using template {template.name} and params {requestParams}")
            uri = f"{config.baseUri}/api/parts/{quote_plus(meta['doc'])}/json"
            page += 1
            next = _retrieve(config, uri, requestParams, view, page, mapping, output, index)
            while next:
                page += 1
                next = _retrieve(config, uri, requestParams, view, page, mapping, output, index, next)
            config.verbose and typer.echo("\n")
    _save(output, mapping)

def _retrieve(config: Config, uri: str, reqParams: dict, view: str, page: int, mapping: dict, 
    output: Path, index: str = None, root: dict = None):
    params = dict(reqParams)
    root and params.update(root)

    resp = requests.get(uri, params=params)
    if not resp.status_code == 200:
        typer.secho(f"\n{resp.text}", color=typer.colors.RED)
        return
    data = resp.json()
    fileId = f"{view}-{page}"
    fileName = f"{fileId}.json"
    file = Path(output, fileName)
    
    if config.verbose:
        typer.echo(f"\rWriting page: {typer.style(str(page), fg=typer.colors.BLUE)}", nl=False)

    content = _expandLinks(config, data['content'])
    
    index and _index(config, index, content, data, output)

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

def _index(config: Config, selector: str, content: BeautifulSoup, info: dict, path: Path):
    """Create index entries for the given content in a jsonl file, which will be
    loaded into the in-browser search engine."""
    relPath = path.relative_to(config.baseDir)
    if info.get('id'):
        params = f"?id={info['id']}"
    else:
        params = f"?root={info['root']}"
    blocks = content.select(selector);
    with open(Path(config.baseDir, 'index.jsonl'), 'a', encoding="UTF-8") as jsonl:
        for block in blocks:
            text = block.get_text()
            if text != "":
                context = block.find_parent(('div', 'section'), attrs={ 'data-tei': True })
                divWithId = block.find_parent(('div', 'section'), attrs={ 'id': True })
                id = '' if divWithId == None else divWithId['id']
                doc = {
                    'path': f"{config.context}{str(relPath)}{params}#{id}",
                    'context': context['data-tei'] if context else None,
                    'content': block.get_text(),
                    'title': block.name in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6')
                }
                json.dump(doc, jsonl, ensure_ascii=False)
                jsonl.write('\n')

def _load(config: Config, uriTemplate: str, output: Path, meta: dict):
    """Download a single resource from the given expanded URI and store it

    Args:
        config (Config): the global configuration
        uriTemplate (str): URI to fetch from - will be expanded via templating
        output (Path): the output file to save into
        meta (dict): parameters to be passed to the URI template

    Returns:
        _type_: _description_
    """
    uri = expandTemplateString(uriTemplate, meta)
    if config.verbose:
        typer.echo(f"Downloading {typer.style(uri, fg=typer.colors.GREEN)} to {output}")
    url = urljoin(config.baseUri, uri)
    resp = requests.get(url)
    with open(output, 'w', encoding="UTF-8") as f:
        resp.encoding = "UTF-8"
        f.write(resp.text)
    return uri

def _loadMap(output: Path):
    """Load an existing `index.json` map or create an empty map

    Args:
        output (Path): directory to check

    Returns:
        dict: contents of the existing map or an empty dict
    """
    indexPath = Path(output, 'index.json')
    if indexPath.exists():
        with open(indexPath, 'r') as f:
            return json.load(f)
    return {}

def _loadMeta(baseUri: str, doc: str) -> dict:
    """Contact TEI Publisher API to retrieve basic metadata about
    the specified document. This includes: used ODD, preferred view and template.

    Args:
        baseUri (str): TEI Publisher base URI
        doc (str): relative document path

    Returns:
        dict: metadata returned by endpoint
    """
    resp = requests.get(f"{baseUri}/api/document/{quote_plus(doc)}/meta")
    if resp.status_code != 200:
        typer.echo(typer.style(f"\nSkipping document: {doc}!", fg=typer.colors.RED))
        return None
    return resp.json()

def _checkCSS(meta: dict, config: Config) -> None:
    """Check if the CSS styles for the used ODD were already downloaded
    and fetch them if not.

    Args:
        meta (dict): document metadata referencing the ODD
        config (Config): global configuration object
    """
    if meta.get('odd'):
        file = f"{meta['odd'][:-4]}.css"
        path = Path(config.baseDir, 'css', file)
        if not path.exists():
            resp = requests.get(f"{config.baseUri}/transform/{file}")
            if resp.status_code == 200:
                if config.verbose:
                    typer.echo(f"Copying {file} to {path}.")
                makedirs(Path(config.baseDir, 'css'), exist_ok=True)
                with open(path, 'w') as f:
                    f.write(resp.text)
            else:
                typer.echo(typer.style(f"Stylesheet {file} not found", fg=typer.colors.MAGENTA))

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
                absolute = urljoin('/' if config.context == '' else config.context, url)
                link['href'] = absolute
    return soup

def _getKey(params: dict) -> str:
    """Generate a key from the passed in parameters to be used for
    the URL mapping. Parameters are sorted alphabetically.

    Args:
        params (dict): the parameters

    Returns:
        str: resulting key
    """
    encParams = []
    for key in sorted(params):
        encParams.append(f"{key}={params[key]}")
    return "&".join(encParams)    

def _save(output, mapping):
    """Save the URI mapping for the document into `index.json`

    Args:
        output (Path): output directory
        mapping (dict): URI mapping to save
    """
    mapFile = Path(output, 'index.json')
    with open(mapFile, 'w') as f:
        json.dump(mapping, f, ensure_ascii=False, indent=4)