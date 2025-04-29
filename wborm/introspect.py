def introspect_table(tablename, conn):
    sql = f"""
    SELECT
        c.colname AS name,
        CASE WHEN c.coltype = 0 THEN 'CHAR' WHEN c.coltype = 1 THEN 'SMALLINT' WHEN c.coltype = 2 THEN 'INTEGER' WHEN c.coltype = 3 THEN 'FLOAT' 
WHEN c.coltype = 4 THEN 'SMALLFLOAT' WHEN c.coltype = 5 THEN 'DECIMAL' WHEN c.coltype = 6 THEN 'SERIAL' WHEN c.coltype = 7 THEN 'DATE' WHEN c.coltype = 8 THEN 'MONEY' 
WHEN c.coltype = 9 THEN 'NULL' WHEN c.coltype = 10 THEN 'DATETIME' WHEN c.coltype = 11 THEN 'BYTE' WHEN c.coltype = 12 THEN 'TEXT' WHEN c.coltype = 13 THEN 'VARCHAR' 
WHEN c.coltype = 14 THEN 'INTERVAL' WHEN c.coltype = 15 THEN 'NCHAR' WHEN c.coltype = 16 THEN 'NVARCHAR'WHEN c.coltype = 17 THEN 'INT8' WHEN c.coltype = 18 THEN 'SERIAL8' 
WHEN c.coltype = 19 THEN 'SET' WHEN c.coltype = 20 THEN 'MULTISET' WHEN c.coltype = 21 THEN 'LIST' WHEN c.coltype = 22 THEN 'Unnamed ROW' WHEN c.coltype = 40 THEN 'LVARCHAR' 
WHEN c.coltype = 41 THEN 'CLOB' WHEN c.coltype = 43 THEN 'BLOB' WHEN c.coltype = 44 THEN 'BOOLEAN' WHEN c.coltype = 256 THEN 'CHAR' WHEN c.coltype = 257 THEN 'SMALLINT' 
WHEN c.coltype = 258 THEN 'INTEGER' WHEN c.coltype = 259 THEN 'FLOAT' WHEN c.coltype = 260 THEN 'REAL' WHEN c.coltype = 261 THEN 'DECIMAL' WHEN c.coltype = 262 THEN 'SERIAL' 
WHEN c.coltype = 263 THEN 'DATE' WHEN c.coltype = 264 THEN 'MONEY' WHEN c.coltype = 266 THEN 'DATETIME' WHEN c.coltype = 267 THEN 'BYTE' WHEN c.coltype = 268 THEN 'TEXT' 
WHEN c.coltype = 269 THEN 'VARCHAR' WHEN c.coltype = 270 THEN 'INTERVAL' WHEN c.coltype = 271 THEN 'NCHAR' WHEN c.coltype = 272 THEN 'NVARCHAR'WHEN c.coltype = 273 THEN 'INT8' 
WHEN c.coltype = 274 THEN 'SERIAL8' WHEN c.coltype = 275 THEN 'SET' WHEN c.coltype = 276 THEN 'MULTISET' WHEN c.coltype = 277 THEN 'LIST' WHEN c.coltype = 278 THEN 'Unnamed ROW' 
WHEN c.coltype = 296 THEN 'LVARCHAR' WHEN c.coltype = 297 THEN 'CLOB' WHEN c.coltype = 298 THEN 'BLOB' WHEN c.coltype = 299 THEN 'BOOLEAN' WHEN c.coltype = 4118 THEN 'Named ROW'
END AS type,
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