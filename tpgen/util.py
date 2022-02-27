from pathlib import Path
from shutil import rmtree
from os import makedirs
from typing import List
from typer import echo, secho, style, colors
from urllib.parse import urljoin
from jinja2 import Environment, FileSystemLoader, Template, select_autoescape
import yaml
import requests
import glob

jinija = Environment(
    loader=FileSystemLoader(searchpath="templates"), 
    autoescape=select_autoescape(enabled_extensions=('html', 'xml'), default_for_string=True)
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
    return template.render(params)

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
    content = template.render(params)
    with open(Path(output, 'index.html'), "w", encoding="UTF-8") as f:
        f.write(content)
    return template.name

class Config:
    """Central configuration class initialized from YAML config file
    """

    def __init__(self, config: Path, baseUri: str, baseDir: Path, verbose: bool = False) -> None:
        self.baseUri = baseUri
        self.baseDir = baseDir
        self.context = '/'
        self.collection = True
        self.verbose = verbose
        with open(config, 'r') as f:
            data = yaml.load(f, Loader=yaml.FullLoader)
            if data.get('collection') == False:
                self.collection = False
            self.variables = data.get('variables')
            self.baseUri = self.variables.get('remote') or baseUri
            self.baseDir = self.variables.get('baseDir') or baseDir
            self.components = data.get('components') or 'latest'
            self.templates = data.get('templates')
            self.pages = data.get('pages')
            self.assets = data.get('assets')

            if self.variables.get('context'):
                stripped = self.variables.get('context').strip('/')
                self.context = f"/{stripped}/"
                self.baseDir = Path(self.baseDir, stripped)
            if self.variables.get('title'):
                echo(f"Fetching: {style(self.variables['title'], colors.GREEN)}")

    def loadAssets(self):
        if self.assets:
            for asset in self.assets:
                outputPath = Path(self.baseDir, asset)
                makedirs(outputPath.parent, exist_ok=True)
                
                url = expandTemplateString(self.assets[asset], self.variables)
                url = urljoin(self.baseUri, url)
                resp = requests.get(url)
                if resp.status_code == 200:
                    with open(outputPath, "wb") as f:
                        f.write(resp.content)
        self._copyScripts()
    
    def _copyScripts(self):
        outDir = Path(self.baseDir, 'scripts')
        makedirs(outDir, exist_ok=True)
        for file in glob.glob('templates/scripts/*.js'):
            path = Path(file).relative_to('templates')
            template = jinija.get_template(str(path))
            output = template.render(self.variables)
            with open(Path(outDir, path.name), 'w', encoding="UTF-8") as f:
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