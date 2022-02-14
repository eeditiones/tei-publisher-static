# Static Site Generator for TEI Publisher

**Work in Progress** - status: functional, but not complete

This repository contains a static site generator for TEI Publisher. It can basically create a static version of a website by pre-generating all content. It does so by traversing the site's content via TEI Publishers public API.

## Installation

The generator is written in Python and requires Python 3.

1. clone the repository
2. install dependencies:
   ```pip3 install -r requirements.txt```

## How does it work?

The generator first traverses the collection hierarchy recursively, downloading the HTML view for each page of documents to show. The retrieved content is stored into `static/collections`. It then inspects the HTML to collect the documents to be fetched.

For each document, the generator performs the following operations:

1. ask the server which HTML template and view mode ('div', 'page', 'single') should be used for the particular document
2. try to find an HTML template with the same name in `templates`. If there is no local correspondance, it falls back to the default template: `view.html`
3. check if there is a configuration for the named template in `config.yml`, listing the different views to fetch data for
4. walk through all pages of the document (as a user would do), downloading their HTML content to the output folder