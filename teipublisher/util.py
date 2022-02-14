from pathlib import Path
from shutil import rmtree
from os import makedirs
from typer import echo, secho, style, colors
from urllib.parse import urljoin
from jinja2 import Environment
import yaml
import requests

jinija = Environment()

def expandTemplateString(template: str, params: dict):
    template = jinija.from_string(template)
    return template.render(params)

class Config:
    
    def __init__(self, config: Path, baseUri: str, baseDir: Path) -> None:
        self.baseUri = baseUri
        self.baseDir = baseDir
        with open(config, 'r') as f:
            data = yaml.load(f, Loader=yaml.FullLoader)
            self.baseUri = data.get('remote') or baseUri
            self.baseDir = data.get('baseDir') or baseDir
            self.components = data.get('components') or 'latest'
            self.templates = data.get('templates')
            self.assets = data.get('assets')
    
    def loadAssets(self):
        if self.assets:
            for asset in self.assets:
                outputPath = Path(self.baseDir, asset)
                print(f"writing {self.baseDir}")
                makedirs(outputPath.parent, exist_ok=True)
                
                url = expandTemplateString(self.assets[asset], {
                    'remote': self.baseUri
                })
                resp = requests.get(url)
                if resp.status_code == 200:
                    with open(outputPath, "wb") as f:
                        f.write(resp.content)

def createDirectory(baseDir: str, path: str, clear: bool = False):
    outDir = Path(baseDir, path) if path else baseDir
    if clear and outDir.exists():
        rmtree(outDir, ignore_errors=True)
    echo(f"Creating output directory {style(str(outDir), fg=colors.BLUE)}")
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