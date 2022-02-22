# Static Site Generator for TEI Publisher

**Work in Progress** - status: functional, but not complete.

This repository contains a static site generator for TEI Publisher. It can basically create a static version of a website by pre-generating all content. It does so by traversing the site's content via TEI Publishers public API, transforming all documents via the associated ODDs and storing the output into the file system. The result is a website without dynamic content: neither eXist-db nor TEI Publisher are required.

Obviously the generated website will lack some of the functionality, which requires a database backend, in particular:

* no search facility
* no facetted browsing

On the upside, the resulting HTML files can be hosted on any webserver at small or no cost (e.g. using github pages). Most web components and page layouts will still work as before. A static site is thus a viable option for small editions with a strong focus on the text presentation and requiring less advanced features.

## Installation

The generator is written in Python and requires Python 3. Until TEI Publisher 8 is released, you also need a development build of TEI Publisher (master branch).

1. clone the repository
2. install dependencies:
   ```pip3 install -r requirements.txt```

## Running

To recursively fetch an entire site, simply run

```sh
python3 -m tpgen collection --recursive
```

The `--recursive` option will automatically fetch the content of all documents. Skip it to just retrieve the collection listing.

Once you generated the collections, you can also update a single document:

```sh
python3 -m tpgen document test/F-rom.xml
```

### Launch a Simple Webserver

To see the result you can launch the built-in webserver of Python:

```sh
python3 -m tpgen serve --port 8001
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

Because the result should be a static website, the HTML templates used are necessarily different than the ones within TEI Publisher, though it should be easy enough to copy/paste and then modify the relevant bits. The static templates use the [Jinja](https://jinja.palletsprojects.com/en/3.0.x/templates/) templating framework.

The existing templates in `templates` have been directly copied from TEI Publisher and then modified to match the different templating framework. When copying HTML, it is important to pay attention to the following caveats:

* while the HTML templates in TEI Publisher must be valid XHTML, the static templates are HTML5. You should thus not use closed empty elements. For example, `<pb-param name="..." value="..."/>` should be changed to `<pb-param name="..." value="..."></pb-param>`. Also, auto-closing HTML elements like `<link>` should not be closed with `</link>`
* add an additional attribute `static` to any `pb-view` and `pb-load` web component, instructing the components to rewrite URLs in order to retrieve content from a static server

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

You can use any of the variables declared in the `variables` section of `config.yml` as well as the variables `doc`, `odd` and `view`, which are set to the corresponding values reported by the server for the current document.

The general approach to take when converting a working HTML template from TEI Publisher is as follows:

1. create a static template by copying/pasting the relevant bits from your TEI Publisher template, obeying the rules given above (see 'Templates')
2. in `config.yml` add an entry below `templates` with the name of your template
3. for each `pb-view` in the template add a view configuration as shown for `documentation.html` above:
   * every `pb-param` should be defined as a request param, prefixed by `user.`
   * if your `pb-view` uses a different ODD or view than the one defined as default for the document, add it as parameter as well
4. for each `pb-load`, create an additional mapping using the original URL as value and an arbitrary filename as key (e.g. `toc.html`), then use this key as the `@url` attribute of `pb-param`