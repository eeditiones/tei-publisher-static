from os import makedirs
from typing import Optional
import typer
from pathlib import Path
from shutil import rmtree
import tpgen.document
import tpgen.collection
import tpgen.pages
from tpgen import __version__
from tpgen.util import Config, expandTemplate, selectTemplate
import http.server
import socketserver
from functools import partial

app = typer.Typer()

@app.command()
def pages(
    baseUri: Optional[str] = typer.Option('http://localhost:8080/exist/apps/tei-publisher/', help='TEI Publisher base URI'),
    outDir: Optional[Path] = typer.Option('static', '--out', '-o', help='Output directory'),
    configFile: Optional[Path] = typer.Option('config.yml', '--config', '-c', help="Configuration file to use")
):
    config = Config(configFile, baseUri, outDir)
    config.loadAssets()
    tpgen.pages.fetch(config)

@app.command()
def document(
    doc: str, 
    baseUri: Optional[str] = typer.Option('http://localhost:8080/exist/apps/tei-publisher/', help='TEI Publisher base URI'),
    outDir: Optional[Path] = typer.Option('static', '--out', '-o', help='Output directory'),
    configFile: Optional[Path] = typer.Option('config.yml', '--config', '-c', help="Configuration file to use")
):
    config = Config(configFile, baseUri, outDir)
    config.loadAssets()
    tpgen.document.fetch_document(config, doc)

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
    documents = tpgen.collection.fetch(config, path)
    if recurse:
        for doc in documents:
            tpgen.document.fetch_document(config, doc)

@app.command()
def clean(
    outDir: Optional[Path] = typer.Option('static', help='Output directory'),
):
    typer.echo(f"Deleting output directory {typer.style(str(outDir), typer.colors.BLUE)}")
    outDir.exists() and rmtree(outDir)

@app.command()
def serve(
    outDir: Optional[Path] = typer.Option('static', help='Output directory'),
    port: Optional[int] = typer.Option(8080, '--port', '-p', help='Port to listen on')
):
    Handler = partial(http.server.SimpleHTTPRequestHandler, directory=outDir)

    with socketserver.TCPServer(("", port), Handler) as httpd:
        typer.echo(f"Listening on {httpd.server_address[0]}:{httpd.server_address[1]}")
        httpd.serve_forever()

def _version(version: bool):
    if version:
        typer.echo(f"V {__version__}")
        raise typer.Exit()
    
@app.callback()
def main(version: Optional[bool] = typer.Option(None, '--version', '-v', help="Show version and exit.", is_eager=True, callback=_version)) -> None:
    """Generate a static app from an existing TEI Publisher application.
    """
    return

if __name__ == "__main__":
    app()