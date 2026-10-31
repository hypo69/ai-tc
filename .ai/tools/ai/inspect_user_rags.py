from logger import logger
import sqlite3
for dbpath in ['src/ai/gemini/user_rags/user_rag_1.db', 'src/ai/gemini/user_rags/user_rag_anon_10.0.0.4.db']:
    conn = sqlite3.connect(dbpath)
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    logger.console(f'--- {dbpath} ---')
    logger.console('Tables:', [t[0] for t in tables])
    for t in tables:
        cnt = conn.execute(f'SELECT COUNT(*) FROM {t[0]}').fetchone()[0]
        cols = [c[1] for c in conn.execute(f'PRAGMA table_info({t[0]})').fetchall()]
        logger.console(f'  {t[0]}: {cnt} rows, cols={cols}')
        if cnt > 0:
            row = conn.execute(f'SELECT * FROM {t[0]} LIMIT 1').fetchone()
            for i, c in enumerate(cols):
                val = row[i]
                if not isinstance(val, bytes):
                    logger.console(f'    {c}: {str(val)[:200]}')
    conn.close()
