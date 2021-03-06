"""
Copyright (c) 2015 Civic Knowledge. This file is licensed under the terms of the
Revised BSD License, included in this distribution as LICENSE.txt
"""

from old.fetch import download_and_cache, get_file_from_zip
from old.sourcespec import SourceSpec
from rowgenerators.exceptions import SourceError
from rowgenerators.util import real_files_in_zf, DelayedFlo

custom_proto_map = {}
custom_type_map = {}

def register_proto(proto, clz):
    custom_proto_map[proto] = clz

def register_type(name, clz):
    custom_type_map[name] = clz

def PROTO_TO_SOURCE_MAP():

    d =  {
        'program': ProgramSource,
        'ipynb': NotebookSource,
        'shape': ShapefileSource,
        'metatab': MetapackSource,
        'metapack': MetapackSource,
    }

    d.update(custom_proto_map)

    return d

def TYPE_TO_SOURCE_MAP():
    d =  {
        'gs': CsvSource,
        'csv': CsvSource,
        'socrata': CsvSource,
        'metapack': MetapackSource,
        'tsv': TsvSource,
        'fixed': FixedSource,
        'txt': FixedSource,
        'xls': ExcelSource,
        'xlsx': ExcelSource,
        'shape': ShapefileSource,
        'metatab': MetapackSource,
        'ipynb': NotebookSource
    }

    d.update(custom_type_map)

    return d



