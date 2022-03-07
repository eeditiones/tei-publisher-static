# Static Site Generator for TEI Publisher

**Work in Progress** - status: functional, but limited testing

This repository contains a static site generator for TEI Publisher. It can basically create a static version of a website by pre-generating all content. It does so by traversing the site's content via TEI Publishers public API, transforming all documents via the associated ODDs and storing the output into the file system. The result is a website without dynamic content: neither eXist-db nor TEI Publisher are required.

Obviously the generated website will lack some of the functionality, which requires a database backend, in particular:

* simple client-side search only
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
python3 -m tpgen build
```

You can also specify a different configuration with

```sh
python3 -m tpgen build -c guidelines.yml
```

The `build` command includes the following tasks (if defined in the configuration):

1. fetch all *assets* (if any) and store them into the configured output directory
2. if enabled: recursively scan the *root data collection* of the application. This will store the information to be displayed in the document browser, which - by default - is the main entry point into a TEI Publisher application. 
3. traverse and download all documents found during the collection scan by following links from the collection listing
4. fetch additional pages as defined in the *pages* section. Those are pages which do not directly correspond to a single TEI document listed in the document browser and therefore won't be processed by step 3.

For testing purposes you can also call steps 2 to 4 separately using the following commands:

### Fetch a collection:

```sh
python3 -m tpgen collection -r
```

Without the `-r|--recursive` option, only the collection listing for the document browser will be fetched, not the content of the documents linked from it. You can optionally specify a relative path to the root collection to fetch, e.g. `playground` if you only want documents from TEI Publisher's *playground* collection.

### Fetch/update a single document specified by relative path:

```sh
python3 -m tpgen document test/F-rom.xml
```

### Retrieve separately defined pages only:

```sh
python3 -m tpgen pages
```

### Launch a Simple Webserver

To see the result you can launch the built-in webserver of Python:

```sh
python3 -m tpgen serve --port 8001
```

## How does it work?

The main collection task traverses the collection hierarchy recursively, downloading the HTML view for each page of documents to show. The retrieved content is stored into `static/collections`. It then inspects the HTML to collect the documents to be fetched.

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

The different tasks can be configured via a YAML configuration file (default: `config.yml`). 

## `variables` section

On top this defines various variables, which will be passed on to the templating system. You can add your own variables here and use them in your templates.

Important variables are:

Variable | Description
---------|----------
 remote | Base URL of the TEI Publisher instance to fetch data from
 context | the prefix path under which the static content will be available

### `templates` section

The `templates` section defines the data to be fetched for a given HTML template. A template may include more than one view on the content (i.e. multiple `pb-view` or `pb-load` components). You can thus define a series of different views in `data`, each using a different configuration, corresponding to the HTTP parameters to be sent with the request. For example, take the `documentation.html` template configuration:

```yaml
documentation.html:
   data:
      main:
      breadcrumbs:
         user.mode: breadcrumbs
      toc.html: "{{remote}}api/document/{{doc}}/contents?target=transcription&icons=false"
      documentation.css: "{{remote}}templates/pages/documentation.css"
```

Here the main text view does not require additional parameters, which are thus left empty. However, the page includes a `pb-view` for breadcrumbs and this needs to set the parameter `mode` to `breadcrumbs`. There's also a `pb-load` for the table of contents, which only needs to be retrieved once for the document and is stored into `doc.html`. Finally, we download some additional CSS and store it as well.

You can use any of the variables declared in the `variables` section of `config.yml` as well as the variables `doc`, `odd` and `view`, which are set to the corresponding values reported by the server for the current document. Additional per-template variables can also be defined:

```yaml
documentation.html:
   variables:
      title: "TEI Publisher Documentation"
   data:
      ...
```

### `pages` section (optional)

This section defines pages which would not be found by traversing the collection hierarchy. This may include secondary documents like about pages, project documentation etc., or other views on the data like a listing of people, places, abbreviations or a bibliography.

The key of each entry in the pages section defines the output path where the fetched data will be stored. The value is an object. It *must* at least reference an HTML template and either a path to a single TEI document (`doc`) or an API endpoint returning a sequence of items to be processed (`sequence`).

The generator will look up the specified template in the `templates` section and retrieve the views there. If a single document was specified (via `doc`), the template will be instantiated once for the given document. If a sequence is given (via `sequence`), the generator expects an URL, which it will contact to retrieve a sequence of items. The template is called for each item in the sequence.

For example, `guidelines.yml`, which will result in a static version of the TEI Guidelines app, defines the following:

```yaml
pages:
  "":
    template: guidelines_start.html
    doc: p5.xml
  "p5.xml":
    template: guidelines.html
    doc: p5.xml
  "ref":
    template: guidelines_ref.html
    sequence: "api/idents"
    output: "ref/{{ident}}"
```

The first mapping states that the template `guidelines_start.html` should be used as the entry page to the website. A single TEI document (`p5.xml`) is used as input. The second path, `/p5.xml`, gets generated based on the same input document.

The third entry establishes a slightly more complex mapping: instead of outputting a single page, it generates a sequence of different pages based on the information returned by the API endpoint referenced in `sequence`. This endpoint is expected to return a JSON array. Each element in the array should be an object, defining parameter mappings.

For each parameter mapping, the HTML template is instantiated once with the additional parameters and any views it defines are retrieved. The resulting content is stored into the subdirectory path given by the `output` variable. As you can see above, we use the parameter `{{ident}}` as name of the final directory. This is a parameter returned by the endpoint we called to get the sequence (it will correspond to a TEI element or class name).

### `assets` section

This section defines static assets which should be fetched or copied into an output directory. The output directory is specified as the key of each entry and the files to be fetched as a list. 

* **remote resources** should be specified with a full URI. They will be retrieved and directly stored into the output directory.
* **local resources** should either be 
  * a file path, which may be a glob expression (with wildcards) to potentially match multiple files
  * an object with properties `in` and `out`, where `out` denotes the file name of the output file
  
  Text files (Javascript, CSS, HTML, XML) will be treated as templates, i.e. expanded by the templating system before they are stored.

## Workflow

The general approach to take when converting a working HTML template from TEI Publisher is as follows:

1. create a static template by copying/pasting the relevant bits from your TEI Publisher template, obeying the rules given above (see 'Templates')
2. in `config.yml` add an entry below `templates` with the name of your template
3. for each `pb-view` in the template add a view configuration as shown for `documentation.html` above:
   * every `pb-param` should be defined as a request param, prefixed by `user.`
   * if your `pb-view` uses a different ODD or view than the one defined as default for the document, add it as parameter as well
4. for each `pb-load`, create an additional mapping using the original URL as value and an arbitrary filename as key (e.g. `toc.html`), then use this key as the `@url` attribute of `pb-param`