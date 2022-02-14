# Static Site Generator for TEI Publisher

**Work in Progress** - status: functional, but not complete

This repository contains a static site generator for TEI Publisher. It can basically create a static version of a website by pre-generating all content. It does so by traversing the site's content via TEI Publishers public API. The result is a website without dynamic content: neither eXist-db nor TEI Publisher are required.

## Installation

The generator is written in Python and requires Python 3.

1. clone the repository
2. install dependencies:
   ```pip3 install -r requirements.txt```

## Running

To recursively fetch an entire site, simply run

```sh
python3 main.py collection --recursive
```

## How does it work?

The generator first traverses the collection hierarchy recursively, downloading the HTML view for each page of documents to show. The retrieved content is stored into `static/collections`. It then inspects the HTML to collect the documents to be fetched.

For each document, the generator performs the following operations:

1. ask the server which HTML template and view mode ('div', 'page', 'single') should be used for the particular document
2. create an output directory below `static`, reflecting the relative path to the document in TEI Publisher. For example, output for `test/graves6.xml` will be stored into `static/test/graves6.xml/`.
3. try to find an HTML template with the same name in `templates`. If there is no local correspondance, it falls back to the default template: `view.html`. Expand the template and store the result as `index.html` into the output directory.
4. check if there is a configuration for the named template in `config.yml`, listing the different views to fetch data for
5. walk through all pages of the document (as a user would do), downloading their HTML content to the output folder

## Templates

Because the result should be a static website, the HTML templates used are necessarily different than the ones within TEI Publisher, though it should be easy enough to copy/paste and then modify the relevant bits.

The static templates use the [Jinja](https://jinja.palletsprojects.com/en/3.0.x/templates/) templating framework.

## Configuration

All configuration is done via `config.yml`. Since a template may include more than one view on the content (i.e. multiple `pb-view` or `pb-load` components), you can define a series of different views, each using a different configuration, corresponding to the HTTP parameters to be sent with the request. For example, take the `documentation.html` template configuration:

```yaml
documentation.html:
    main:
    breadcrumbs:
      user.mode: breadcrumbs
    toc.html: "{{remote}}api/document/{{doc}}/contents?target=transcription&icons=false"
    documentation.css: "{{remote}}templates/pages/documentation.css"
```

Here the main text view does not require additional parameters, which are thus left empty. However, the page includes a `pb-view` for breadcrumbs and this needs to set the parameter `mode` to `breadcrumbs`. There's also a `pb-load` for the table of contents, which only needs to be retrieved once for the document and is stored into `doc.html`. Finally, we download some additional CSS and store it as well.