const indexData = [];
const headings = {};

function kwicText(str, start, end, words = 5) {
    let p0 = start - 1;
    let count = 0;
    while (p0 >= 0) {
        if (/[\p{P}\s]/.test(str.charAt(p0))) {
            while (p0 > 1 && /[\p{P}\s]/.test(str.charAt(p0 - 1))) {
                p0 -= 1;
            }
            count += 1;
            if (count === words) {
                break;
            }
        }
        p0 -= 1;
    }
    let p1 = end + 1;
    count = 0;
    while (p1 < str.length) {
        if (/[\p{P}\s]/.test(str.charAt(p1))) {
            while (p1 < str.length - 1 && /[\p{P}\s]/.test(str.charAt(p1 + 1))) {
                p1 += 1;
            }
            count += 1;
            if (count === words) {
                break;
            }
        }
        p1 += 1;
    }
    return `... ${str.substring(p0, start)}<mark>${str.substring(start, end)}</mark>${str.substring(end, p1 + 1)} ...`;
}

function breadcrumbs(context, elem) {
    const spans = [];
    let heading = headings[context];
    while (heading) {
        const span = document.createElement('span');
        span.className = 'breadcrumb';
        span.innerHTML = heading;
        spans.push(span);

        const p = context.lastIndexOf('.');
        if (p > -1) {
            context = context.substring(0, p);
            heading = headings[context];
        } else {
            break;
        }
    }

    spans.reverse().forEach((span) => elem.appendChild(span));
}

function search(index, query) {
    const results = document.getElementById('results');
    results.innerHTML = '';
    index.search(query).then((result) => {
        const tokens = [query, ...query.split(/\W+/)];
        const regex = new RegExp(tokens.join('|'), 'gi');
        result.forEach((idx) => {
            const data = indexData[idx];

            const div = document.createElement('div');
            const head = document.createElement('h3');
            const link = document.createElement('a');
            link.href = data.path;
            head.appendChild(link);
            breadcrumbs(data.context, link);
            div.appendChild(head);

            const list = document.createElement('ul');
            let matches = Array.from(data.content.matchAll(regex));
            if (matches.length > 10) {
                matches = matches.slice(0, 10);
            }
            for (const match of matches) {
                const kwic = kwicText(data.content, match.index, match.index + match[0].length, 10);
                const li = document.createElement('li');
                li.innerHTML = kwic;
                list.appendChild(li);
            }
            div.appendChild(list);

            results.appendChild(div);
        });
    });
}

window.addEventListener('WebComponentsReady', function() {

    const params = new URLSearchParams(location.search);
    const query = params.get('query');
    if (query) {
        document.getElementById('search-input').value = query;
    }
    
    const index = new FlexSearch.Worker({
        tokenize: "reverse"
    });

    pbEvents.subscribe('pb-load', null, (ev) => {
        const query = ev.detail.params.query;
        search(index, query);
    });

    pbEvents.emit('pb-start-update', 'transcription');
    fetch('{{context}}/index.jsonl')
    .then((response) => {
        if (!response.ok) {
            throw new Error('Network response was not OK');
        }
        return response.text();
    }).then((text) => {
        const chunks = text.split('\n');
        chunks.forEach((chunk, idx) => {
            if (chunk.length === 0) {
                return;
            }
            try {
                const data = JSON.parse(chunk);
                indexData.push(data);
                index.add(idx, data.content);

                if (data.title) {
                    headings[data.context] = data.content;
                }
            } catch (e) {
                console.log('error parsing "%s"', chunk);
            }
        });

        if (query) {
            search(index, params.get('query'));
        }
        pbEvents.emit('pb-end-update', 'transcription');
    }).catch(error => {
        console.log(error);
        document.getElementById('results').innerHTML = 'Request failed!';
    });
});