from django.core.management.base import BaseCommand
from django.db import connections


class Command(BaseCommand):
    help = "Fixes all sequences to yield non-existing keys afterwards"

    def handle(self, **options):
        cursor = connections["default"].cursor()

        # Thanks, https://wiki.postgresql.org/wiki/Fixing_Sequences
        cursor.execute(
            """
SELECT
 'SELECT SETVAL(' ||
 quote_literal(quote_ident(PGT.schemaname) || '.' || quote_ident(S.relname)) ||
 ', COALESCE(MAX(' ||quote_ident(C.attname)|| '), 1) ) FROM ' ||
 quote_ident(PGT.schemaname)|| '.'||quote_ident(T.relname)|| ';'
FROM
 pg_class AS S,
 pg_depend AS D,
 pg_class AS T,
 pg_attribute AS C,
 pg_tables AS PGT
WHERE S.relkind = 'S'
 AND S.oid = D.objid
 AND D.refobjid = T.oid
 AND D.refobjid = C.attrelid
 AND D.refobjsubid = C.attnum
 AND T.relname = PGT.tablename
ORDER BY S.relname"""
        )

        statements = list(cursor)

        for row in statements:
            self.stdout.write(row[0])
            cursor.execute(row[0])
