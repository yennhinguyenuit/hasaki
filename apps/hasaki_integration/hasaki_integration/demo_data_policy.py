"""The only permitted runtime difference in deployment preservation checks."""


def allowed_runtime_changes(changes):
    return all(doctype == 'User' and all(set(row['fields']) <= {'last_active'} for row in rows)
               for doctype, rows in changes.items())
