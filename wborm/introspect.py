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
JOIN systables fk ON c.tabid = fk.tabid
JOIN systables pk ON r.ptabid = pk.tabid
-- Índices: FK -> idxname (da tabela filha), PK -> primary (da tabela pai)
JOIN sysindexes idx_fk ON idx_fk.idxname = c.idxname AND idx_fk.tabid = c.tabid
JOIN sysindexes idx_pk ON idx_pk.idxname = r.primary AND idx_pk.tabid = r.ptabid
-- Colunas envolvidas no índice FK (filha)
JOIN syscolumns fc ON fc.tabid = fk.tabid AND fc.colno IN (
    idx_fk.part1, idx_fk.part2, idx_fk.part3, idx_fk.part4,
    idx_fk.part5, idx_fk.part6, idx_fk.part7, idx_fk.part8,
    idx_fk.part9, idx_fk.part10, idx_fk.part11, idx_fk.part12,
    idx_fk.part13, idx_fk.part14, idx_fk.part15, idx_fk.part16
)
-- Colunas envolvidas no índice PK (pai)
JOIN syscolumns pc ON pc.tabid = pk.tabid AND pc.colno IN (
    idx_pk.part1, idx_pk.part2, idx_pk.part3, idx_pk.part4,
    idx_pk.part5, idx_pk.part6, idx_pk.part7, idx_pk.part8,
    idx_pk.part9, idx_pk.part10, idx_pk.part11, idx_pk.part12,
    idx_pk.part13, idx_pk.part14, idx_pk.part15, idx_pk.part16
)
WHERE c.constrtype = 'R'
  AND (
    COALESCE(TRIM(fk.tabname), '') = '{tablename}'
    OR COALESCE(TRIM(pk.tabname), '') = '{tablename}'
  )
  AND idx_fk.part1 IS NOT NULL
  AND idx_pk.part1 IS NOT NULL
    """
    return conn.execute_query(sql)