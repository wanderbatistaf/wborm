def introspect_table(tablename, conn):
    sql = f"""
    SELECT
        c.colname AS name,
        c.coltype AS type,
        c.collength AS length,
        c.colno AS position
    FROM
        systables t
    JOIN
        syscolumns c ON t.tabid = c.tabid
    WHERE
        t.tabname = '{tablename}'
    ORDER BY c.colno
    """
    return conn.execute_query(sql)

def get_foreign_keys(tablename, conn):
    sql = f"""
    SELECT
        c.constrname,
        TRIM(fk.tabname) AS from_table,
        TRIM(pk.tabname) AS to_table,
        TRIM(fc.colname) AS from_column,
        TRIM(pc.colname) AS to_column
    FROM sysconstraints c
    JOIN sysreferences r ON c.constrid = r.constrid
    JOIN systables fk ON r.tabid = fk.tabid
    JOIN systables pk ON r.ptabid = pk.tabid
    JOIN syscolumns fc ON r.tabid = fc.tabid AND r.colno = fc.colno
    JOIN syscolumns pc ON r.ptabid = pc.tabid AND r.pcolno = pc.colno
    WHERE c.constrtype = 'R'
    AND (fk.tabname = '{tablename}' OR pk.tabname = '{tablename}')
    """
    return conn.execute_query(sql)