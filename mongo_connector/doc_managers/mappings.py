# coding: utf8

from mongo_connector.doc_managers.formatters import DocumentFlattener

from mongo_connector.doc_managers.utils import db_and_collection, ARRAY_OF_SCALARS_TYPE

_formatter = DocumentFlattener()


def _clean_and_flatten_doc(mappings, doc, namespace):
    """Reformats the given document before insertion into Solr.
    This method reformats the document in the following ways:
      - removes extraneous fields that aren't defined in schema.xml
      - unwinds arrays in order to find and later flatten sub-documents
      - flattens the document so that there are no sub-documents, and every
        value is associated with its dot-separated path of keys
      - inserts namespace and timestamp metadata into the document in order
        to handle rollbacks
    An example:
      {"a": 2,
       "b": {
         "c": {
           "d": 5
         }
       },
       "e": [6, 7, 8]
      }
    becomes:
      {"a": 2, "b.c.d": 5, "e.0": 6, "e.1": 7, "e.2": 8}
    """

    # PGSQL cannot index fields within sub-documents, so flatten documents
    # with the dot-separated path to each value as the respective key
    flat_doc = _formatter.format_document(doc)

    # Extract column names and mappings for this table
    db, coll = db_and_collection(namespace)
    if db in mappings:
        mappings_db = mappings[db]
        if coll in mappings_db:
            mappings_coll = mappings_db[coll]

            # Only include fields that are explicitly provided in the schema
            def include_field(field):
                return field in mappings_coll

            return dict((k, v) for k, v in flat_doc.items() if include_field(k))
    return {}


def to_scalar_string(scalar_array):
    return u" --*-- ".join(scalar_array)


def get_mapped_document(mappings, document, namespace):
    cleaned_and_flatten_document = _clean_and_flatten_doc(mappings, document, namespace)

    db, collection = db_and_collection(namespace)
    keys = cleaned_and_flatten_document.keys()

    for key in keys:
        field_mapping = mappings[db][collection][key]

        if 'dest' in field_mapping:
            mappedKey = field_mapping['dest']
            cleaned_and_flatten_document[mappedKey] = cleaned_and_flatten_document.pop(key)

    return cleaned_and_flatten_document


def get_mapped_field(mappings, namespace, field_name):
    db, collection = db_and_collection(namespace)
    return mappings[db][collection][field_name]['dest']


def get_primary_key(mappings, namespace):
    db, collection = db_and_collection(namespace)
    return mappings[db][collection]['pk']


def is_mapped(mappings, namespace, field_name=None):
    db, collection = db_and_collection(namespace)
    return db in mappings and collection in mappings[db] and \
           (field_name is None or field_name in mappings[db][collection])


def is_id_autogenerated(mappings, namespace):
    primary_key = get_primary_key(mappings, namespace)

    db, collection = db_and_collection(namespace)
    mapped_to_primary_key = [k for k, v in mappings[db][collection].iteritems() if
                             'dest' in v and v['dest'] == primary_key]
    return len(mapped_to_primary_key) == 0


def get_scalar_array_fields(mappings, db, collection):
    if db not in mappings or collection not in mappings[db]:
        return []

    return [
        k for k, v in mappings[db][collection].iteritems()
        if 'type' in v and v['type'] == ARRAY_OF_SCALARS_TYPE
        ]
