from pathlib import Path
from shutil import copyfile, rmtree
from os import makedirs
from typing import List
from numpy import isin
from typer import echo, secho, style, colors, Exit
from urllib.parse import urljoin, urlparse
from jinja2 import Environment, FileSystemLoader, Template, select_autoescape, pass_context
import yaml
from jsonschema import validate as json_validate, ValidationError
from mimetypes import guess_type
import json
import requests
import glob
from datetime import datetime

@pass_context
def expand_str(ctx, value) -> str:
    return expandTemplateString(value, ctx.get_all())

jinija = Environment(
    loader=FileSystemLoader(searchpath="templates"), 
    autoescape=select_autoescape(enabled_extensions=('html', 'xml'), default_for_string=True)
)
jinija.filters['expand_str'] = expand_str

textMimeTypes = (
    'application/json', 'application/javascript', 'text/html', 'application/xml', 'text/css', 'text/text',
    'application/markdown'
)

def expandTemplateString(template: str, params: dict) -> str:
    """Expand the given template string via jinija

    Args:
        template (str): string to expand
        params (dict): dictionary with parameters which can be used in template expressions

    Returns:
        str: expanded string
    """
    template = jinija.from_string(template)
    return template.render(_templateInfo(template, params))

def selectTemplate(templates: List) -> Template:
    """Find the first available template by going through the supplied list

    Args:
        templates (List): List of alternative templates

    Returns:
        Template: the template found
    """
    return jinija.select_template(templates)

def expandTemplate(template: Template, meta: dict, output: Path):
    """Expand the given template using parameters passed `meta` and
    write the resulting html to `index.html` below `output`.

    Args:
        template (Template): the Jinija template to use
        meta (dict): dictionary with parameters
        output (Path): output directory

    Returns:
        str: name of the template
    """
    params = dict(meta)
    if meta.get('odd'):
        params['odd'] = meta['odd'][:-4]
    content = template.render(_templateInfo(template, params))
    with open(Path(output, 'index.html'), "w", encoding="UTF-8") as f:
        f.write(content)
    return template.name

def _templateInfo(template: Template, params: dict) -> dict:
    params['page'] = {
        'time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    return params

class Config:
    """Central configuration class initialized from YAML config file
    """

    def __init__(self, config: Path, baseUri: str, baseDir: Path, verbose: bool = False) -> None:
        self.baseUri = baseUri
        self.baseDir = baseDir
        self.context = ''
        self.collection = True
        self.verbose = verbose
        with open(config, 'r') as f:
            data = yaml.load(f, Loader=yaml.FullLoader)
            if not self._validate(data):
                Exit(1)
            if data.get('collection') == False:
                self.collection = False
            self.variables = data.get('variables')
            self.baseUri = self.variables.get('remote') or baseUri
            self.baseDir = self.variables.get('baseDir') or baseDir
            self.components = data.get('components') or 'latest'
            self.templates = data.get('templates')
            self.pages = data.get('pages')
            self.assets = data.get('assets')
            self.worker = data.get('worker')

            if self.variables.get('context'):
                stripped = self.variables.get('context').strip('/')
                self.context = f"/{stripped}/"
                self.baseDir = Path(self.baseDir, stripped)

            if self.variables.get('title'):
                echo(f"Using config: {style(self.variables['title'], colors.GREEN)}")

    def loadAssets(self):
        """Process the `assets` section of the config; fetch or copy the listed resources.
        """
        if not self.assets:
            return
        for asset in self.assets:
            sources = self.assets[asset]
            outputPath = Path(self.baseDir, asset)
            makedirs(outputPath, exist_ok=True)
            
            for source in sources:
                outputFile = None
                if isinstance(source, str):
                    inputFile = source
                else:
                    inputFile = source['in']
                    outputFile = source['out']
                url = expandTemplateString(inputFile, self.variables)
                urlparts = urlparse(url)
                if urlparts.netloc != '':
                    url = urljoin(self.baseUri, url)
                    resp = requests.get(url)
                    if resp.status_code == 200:
                        fileName = outputFile or Path(urlparts.path).name
                        with open(Path(outputPath, fileName), "wb") as f:
                            f.write(resp.content)
                else:
                    files = [inputFile] if outputFile else glob.glob(source)
                    for source in files:
                        sourcePath = Path(source)
                        if guess_type(source)[0] in textMimeTypes:
                            with open(sourcePath, 'r', encoding='UTF-8') as f:
                                expanded = expandTemplateString(f.read(), self.variables)
                            with open(Path(outputPath, outputFile or sourcePath.name), 'w', encoding='UTF-8') as f:
                                f.write(expanded)
                        else:
                            copyfile(sourcePath, outputFile)
    
    def _validate(self, data: dict) -> bool:
        """
            Validate the configuration against the schema in `config-schema.json`.

            Args:
                data: the configuration data as dict
        """
        with open(Path(__package__, 'config-schema.json'), 'r') as f:
            schema = json.load(f)

        try:
            json_validate(data, schema)
        except ValidationError as e:
            echo(f"""
Configuration error: {style(e.message, colors.RED)}
Offending configuration property: {" -> ".join(e.absolute_path)}
            """)
            return False
        return True
    
    def serviceWorker(self):
        if not self.worker:
            return
        precache = []
        if self.worker.get('precache'):
            for pattern in self.worker['precache']:
                url = expandTemplateString(pattern, self.variables)
                urlparts = urlparse(url)
                if urlparts.netloc != '':
                    precache.append(url)
                else:
                    for file in glob.glob(str(self.baseDir) + '/' + url, recursive=True):
                        path = Path(self.context if self.context != '' else '/', Path(file).relative_to(self.baseDir))
                        precache.append(path)
        params = { **self.variables, 'precache': precache }
        template = selectTemplate(['scripts/sw.js'])
        output = template.render(params)
        with open(Path(self.baseDir, 'sw.js'), 'w', encoding='UTF-8') as f:
            f.write(output)

def createDirectory(baseDir: Path, path: str, clear: bool = False):
    outDir = Path(baseDir, path) if path else baseDir
    if clear and outDir.exists():
        rmtree(outDir, ignore_errors=True)
    makedirs(outDir, exist_ok=True)
    return outDir

def loadImages(images, collectionPath: str, config: Config, output: Path):
    base = f"{config.baseUri}{collectionPath or ''}"
    for image in images:
        src = image['src']
        url = urljoin(base, src)
        if url.startswith(base):
            echo(f"Retrieving image {url}")
            resp = requests.get(url)
            if (resp.status_code == 200):
                with open(Path(output, image['src']), 'wb') as f:
                    f.write(resp.content)
            else:
                secho(f"Image {image['src']} not found.", fg=colors.RED)