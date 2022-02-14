from teipublisher.util import createDirectory, loadImages, Config
import typer
from pathlib import Path
import requests
from urllib.parse import quote_plus
from bs4 import BeautifulSoup

def fetch(config: Config, path: str, clear: bool = False, start: int = 1):
    output = createDirectory(Path(config.baseDir, 'collections'), path, clear)
    if path:
        uri = f"{config.baseUri}/api/collection/{quote_plus(path)}"
    else:
        uri = f"{config.baseUri}/api/collection"

    resp = requests.get(uri, params={ 'start': start})
    total = resp.headers.get('pb-total')

    file = Path(output, f"{start}.html")
    typer.echo(f"Writing {typer.style(str(file), fg=typer.colors.BLUE)}")
    subcols = []
    documents = []
    with open(file, mode="w", encoding="UTF-8") as f:
        resp.encoding = "UTF-8"
        content = resp.text
        f.write(content)
        children = _expand(content, path, config, config.baseDir)
        subcols += children['collections']
        documents += children['documents']

    if total and start + 10 < int(total):
        documents += fetch(config, path, clear=clear, start=start + 10)

    for subcol in subcols:
        if path:
            childPath = f"{path}/{subcol}"
        else:
            childPath = subcol
        documents += fetch(config, childPath, clear=clear)
    return documents

def _expand(content, collectionPath: str, config: Config, output: Path):
    soup = BeautifulSoup(content, features='html.parser')

    loadImages(soup.select('img[src]'), collectionPath, config, output)

    links = soup.select('.document a[data-collection]')
    subcols = []
    for link in links:
        subcols.append(link['data-collection'])
    
    documents = []
    links = soup.select('.document a:not([data-collection])')
    for link in links:
        documents.append(link['href'])
    return {
        'documents': documents,
        'collections': subcols
    }