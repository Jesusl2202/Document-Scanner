"""Adaptador opcional Google Document AI. Solo se ejecuta al elegir el motor google."""
import mimetypes
import os
import time
from pathlib import Path
from .common import FIELDS, normalize


def parse_entities(entities, config):
    """Recibe JSON del SDK o exportado. No inventa entidades no devueltas."""
    mapping = config['google']['entity_map']
    evidence = {f: [] for f in FIELDS}
    for entity in entities:
        field = mapping.get(entity.get('type', entity.get('type_', '')))
        if field not in evidence:
            continue
        raw = entity.get('mentionText', entity.get('mention_text', ''))
        if not raw:
            raw = entity.get('textAnchor', entity.get('text_anchor', {})).get('content', '')
        if not raw:
            continue
        evidence[field].append({'value': raw, 'confidence': entity.get('confidence'),
                                'entity_type': entity.get('type', entity.get('type_')),
                                'page_anchor': entity.get('pageAnchor', entity.get('page_anchor'))})
    values, alerts = {}, []
    for field, options in evidence.items():
        distinct = {normalize(field, o['value'], config['normalization']) for o in options}
        values[field] = options[0]['value'] if len(distinct) == 1 else None
        if not options:
            alerts.append(field + ':no_entity')
        elif len(distinct) > 1:
            alerts.append(field + ':ambiguous_entities')
    return {'fields': values, 'evidence': evidence, 'alerts': alerts}


def process(path, config):
    from google.api_core.client_options import ClientOptions
    from google.cloud import documentai
    resource = os.environ.get('DOCUMENTAI_PROCESSOR_RESOURCE', config['google']['processor_resource'])
    if not resource:
        raise ValueError('Configure DOCUMENTAI_PROCESSOR_RESOURCE; no hay procesador de nube por defecto')
    location = resource.split('/locations/')[1].split('/')[0] if '/locations/' in resource else config['google']['location']
    client = documentai.DocumentProcessorServiceClient(client_options=ClientOptions(api_endpoint=f'{location}-documentai.googleapis.com'))
    start = time.perf_counter()
    try:
        request = documentai.ProcessRequest(name=resource, raw_document=documentai.RawDocument(
            content=Path(path).read_bytes(), mime_type=mimetypes.guess_type(path)[0] or 'application/octet-stream'))
        response = client.process_document(request=request, timeout=config['google']['timeout_seconds'], retry=None)
        document = documentai.Document.to_dict(response.document)
    finally:
        client.transport.close()
    result = parse_entities(document.get('entities', []), config)
    result.update({'text': document.get('text', ''), 'provider_response': document,
                   'provider_seconds': time.perf_counter() - start, 'processor_resource': resource})
    return result
