from tpgen.util import Config, expandTemplateString
import typer
import tpgen.document
import requests

def fetch(config: Config):
    if not config.pages:
        return
    for page in config.pages:
        pageConf = config.pages[page]
        typer.echo(f"Processing page /{typer.style(page, typer.colors.MAGENTA)}...")
        if 'doc' in pageConf:
            tpgen.document.fetch_document(config, pageConf['doc'], 
                params={ 'template': pageConf['template'] }, target_path=page, clean=False
            )
        else:
            _fetchSequence(config, pageConf)

def _fetchSequence(config, pageConf):
    sequence = pageConf.get('sequence')
    resp = requests.get(f"{config.baseUri}{sequence}")

    data = resp.json()
    for params in data:
        output = expandTemplateString(pageConf.get('output'), params)
        params['template'] = pageConf['template']
        tpgen.document.fetch(config, params, target_path=output, clean=False)
