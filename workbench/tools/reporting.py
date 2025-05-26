from django.db import connections


def query(sql, params=(), *, as_dict=False):
    with connections["default"].cursor() as cursor:
        cursor.execute(sql, params)
        if as_dict:
            names = [col.name for col in cursor.description]
            return [dict(zip(names, values, strict=True)) for values in cursor]
        return list(cursor)
