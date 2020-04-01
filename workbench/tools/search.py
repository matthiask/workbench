"""
PostgreSQL full text search support

An example migration for adding full text search support to a model would
look like this::

    # -*- coding: utf-8 -*-
    from __future__ import unicode_literals
    from django.db import models, migrations
    from workbench.tools import search

    class Migration(migrations.Migration):
        dependencies = [
            # ...
        ]

        operations = [
            migrations.RunSQL(
                search.create_structure("database_table")
            ),
            migrations.RunSQL(
                search.fts("database_table", ["field1", "field"])
            ),
        ]
"""

import re


def drop_old_shit(table):
    return """\
DROP TRIGGER IF EXISTS {table}_fts_update_trigger ON {table};
DROP TRIGGER IF EXISTS {table}_fts_insert_trigger ON {table};
DROP FUNCTION IF EXISTS {table}_fts_document (integer);
DROP FUNCTION IF EXISTS {table}_fts_document_trigger ();
""".format(
        table=table
    )


def create_structure(table):
    return """\
ALTER TABLE {table} DROP COLUMN IF EXISTS fts_document;
DROP INDEX IF EXISTS {table}_fts_index;

ALTER TABLE {table} ADD COLUMN fts_document tsvector;
CREATE INDEX {table}_fts_index ON {table} USING gin(fts_document);
""".format(
        table=table
    )


def fts(table, fields):
    return """\
CREATE OR REPLACE FUNCTION {table}_fts() RETURNS trigger AS $$
begin
  new.fts_document:=to_tsvector(
    'pg_catalog.german',
    regexp_replace(
      unaccent(concat_ws(' ', {fields})),
      '[^0-9A-Za-z]+',
      ' '
    )
  );
  return new;
end
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS {table}_fts_trigger ON {table};
CREATE TRIGGER {table}_fts_trigger BEFORE INSERT OR UPDATE
  ON {table} FOR EACH ROW EXECUTE PROCEDURE {table}_fts();
""".format(
        table=table, fields=", ".join("new.{}".format(field) for field in fields)
    )


def process_query(s):
    """
    Converts the user's search string into something suitable for passing to
    to_tsquery.
    """
    # noqa Thanks https://www.fusionbox.com/blog/detail/partial-word-search-with-postgres-full-text-search-in-django/632/
    query = re.sub(r"[^-+@\w]+", " ", s).strip()
    if query:
        query = re.sub(r"\s+", " & ", query)
        # Support prefix search on the last word. A tsquery of 'toda:*' will
        # match against any words that start with 'toda', which is good for
        # search-as-you-type.
        query += ":*"
    return query


def search(queryset, terms):
    return (
        queryset.extra(
            where=[
                "%s.fts_document"
                " @@ to_tsquery('pg_catalog.german', unaccent(%%s))"
                % (queryset.model._meta.db_table,)
            ],
            params=[process_query(terms)],
        )
        if terms
        else queryset
    )
