from os import makedirs
from typing import Optional
import typer
from pathlib import Path
from shutil import rmtree
import teipublisher.document
import teipublisher.collection
import teipublisher.pages
from teipublisher.util import Config, expandTemplate, selectTemplate

app = typer.Typer()

@app.command()
def pages(
    baseUri: Optional[str] = typer.Option('http://localhost:8080/exist/apps/tei-publisher/', help='TEI Publisher base URI'),
    outDir: Optional[Path] = typer.Option('static', '--out', '-o', help='Output directory'),
    configFile: Optional[Path] = typer.Option('config.yml', '--config', '-c', help="Configuration file to use")
):
    config = Config(configFile, baseUri, outDir)
    config.loadAssets()
    teipublisher.pages.fetch(config)

@app.command()
def document(
    doc: str, 
    baseUri: Optional[str] = typer.Option('http://localhost:8080/exist/apps/tei-publisher/', help='TEI Publisher base URI'),
    outDir: Optional[Path] = typer.Option('static', '--out', '-o', help='Output directory'),
    configFile: Optional[Path] = typer.Option('config.yml', '--config', '-c', help="Configuration file to use")
):
    config = Config(configFile, baseUri, outDir)
    config.loadAssets()
    teipublisher.document.fetch_document(config, doc)

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

    makedirs(config.baseDir, exist_ok=True)
    template = selectTemplate(['index.html'])
    expandTemplate(template, config.variables, config.baseDir)
    documents = teipublisher.collection.fetch(config, path)
    if recurse:
        for doc in documents:
            teipublisher.document.fetch_document(config, doc)

@app.command()
def clean(
    outDir: Optional[Path] = typer.Option('static', help='Output directory'),
):
    typer.echo(f"Deleting output directory {typer.style(str(outDir), typer.colors.BLUE)}")
    outDir.exists() and rmtree(outDir)

if __name__ == "__main__":
    app()