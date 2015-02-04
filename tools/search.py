"""
PostgreSQL full text search support
"""


def migration_sql(table, fields):
    FORWARD_SQL = '''
CREATE FUNCTION {table}_fts_document(integer) RETURNS tsvector AS $$
DECLARE
 {table}_document TEXT;
BEGIN
 SELECT concat_ws(' ', {fields}) INTO {table}_document
 FROM {table} WHERE id=$1;
 RETURN to_tsvector('pg_catalog.german', {table}_document);
END;
$$ LANGUAGE plpgsql;

CREATE FUNCTION {table}_fts_document_trigger() RETURNS TRIGGER AS $$
BEGIN
 NEW.fts_document={table}_fts_document(NEW.id);
 RETURN NEW;
END;
$$ LANGUAGE plpgsql;

ALTER TABLE {table} ADD COLUMN fts_document tsvector;
UPDATE {table} SET fts_document={table}_fts_document(id);
CREATE TRIGGER {table}_fts_update_trigger BEFORE UPDATE ON {table}
 FOR EACH ROW EXECUTE PROCEDURE {table}_fts_document_trigger();
CREATE TRIGGER {table}_fts_insert_trigger BEFORE INSERT ON {table}
 FOR EACH ROW EXECUTE PROCEDURE {table}_fts_document_trigger();
CREATE INDEX {table}_fts_index ON {table} USING gin(fts_document);
    '''

    BACKWARD_SQL = '''
DROP INDEX {table}_fts_index;
ALTER TABLE {table} DROP COLUMN fts_document;
DROP TRIGGER {table}_fts_update_trigger ON {table};
DROP TRIGGER {table}_fts_insert_trigger ON {table};
DROP FUNCTION {table}_fts_document (integer);
DROP FUNCTION {table}_fts_document_trigger ();
    '''

    return (
        FORWARD_SQL.format(table=table, fields=fields),
        BACKWARD_SQL.format(table=table),
    )


def search(queryset, terms):
    if not terms:
        return queryset
    return queryset.extra(
        where=[
            '%s.fts_document'
            ' @@ plainto_tsquery(\'pg_catalog.german\', %%s)' % (
                queryset.model._meta.db_table,
            ),
        ],
        params=[terms],
    )
