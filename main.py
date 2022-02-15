from os import makedirs
from typing import Optional
import typer
from pathlib import Path
from shutil import rmtree
import teipublisher.document
import teipublisher.collection
from teipublisher.util import Config, expandTemplate

app = typer.Typer()

@app.command()
def document(
    doc: str, 
    baseUri: Optional[str] = typer.Option('http://localhost:8080/exist/apps/tei-publisher/', help='TEI Publisher base URI'),
    outDir: Optional[Path] = typer.Option('static', '--out', '-o', help='Output directory'),
    configFile: Optional[Path] = typer.Option('config.yml', '--config', '-c', help="Configuration file to use")
):
    config = Config(configFile, baseUri, outDir)
    config.loadAssets()
    teipublisher.document.fetch(config, doc, True)

@app.command()
def collection(
    path: Optional[str] = typer.Argument(None),
    baseUri: Optional[str] = typer.Option('http://localhost:8080/exist/apps/tei-publisher/', help='TEI Publisher base URI'),
    outDir: Optional[Path] = typer.Option('static', help='Output directory'),
    recurse: bool = typer.Option(False, '--recursive', '-r', help='Fetch subcollections and documents recursively'),
    configFile: Optional[Path] = typer.Option('config.yml', '--config', '-c', help="Configuration file to use")
):
    config = Config(configFile, baseUri, outDir)
    config.loadAssets()

    makedirs(outDir, exist_ok=True)
    expandTemplate(['index.html'], config.variables, outDir)
    documents = teipublisher.collection.fetch(config, path)
    if recurse:
        for doc in documents:
            teipublisher.document.fetch(config, doc, True)

@app.command()
def clean(
    outDir: Optional[Path] = typer.Option('static', help='Output directory'),
):
    rmtree(outDir)

if __name__ == "__main__":
    app()