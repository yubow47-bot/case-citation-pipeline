"""Deterministic corpus language selection, explicitly bound to each run.

Historical manifests without text_policy keep their original English scope.
New runs prefer English and fall back to French only when English is absent.
This never extracts both texts of a bilingual source judgment.
"""
POLICY_EN = 'english_only'
POLICY_FALLBACK = 'en_then_fr'
POLICIES = (POLICY_EN, POLICY_FALLBACK)
METADATA_FIELDS = tuple(base+'_'+lang for base in ('citation','name','document_date') for lang in ('en','fr'))
TEXT_FIELDS = ('unofficial_text_en','unofficial_text_fr')


def _present(value):
    return bool(value.strip()) if isinstance(value, str) else value is not None


def policy_from_manifest(manifest):
    policy = manifest.get('params', {}).get('text_policy', POLICY_EN)
    if policy not in POLICIES:
        raise ValueError('Unknown corpus text_policy: '+str(policy))
    return policy


def select_record(record, policy=POLICY_EN):
    if policy not in POLICIES:
        raise ValueError('Unknown corpus text_policy: '+str(policy))
    result = {}
    for target, base in (('citation','citation'), ('name','name'), ('date','document_date'), ('text','unofficial_text')):
        field = base+'_en'
        if policy == POLICY_FALLBACK and not _present(record.get(field)) and _present(record.get(base+'_fr')):
            field = base+'_fr'
        value = record.get(field)
        if target != 'date':
            if value is not None and not isinstance(value, str):
                raise ValueError('Corpus '+field+' must be text or null')
            value = value or ''
        result[target] = value
        result[target+'_field'] = field
    result['language'] = result['text_field'].rsplit('_',1)[1]
    return result


def projection(schema_names, include_text=True):
    fields = METADATA_FIELDS + (TEXT_FIELDS if include_text else ())
    return [field for field in fields if field in schema_names]
