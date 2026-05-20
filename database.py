import sqlite3

def connect_to_db():
    conn = sqlite3.connect("link_health.db")
    cur = conn.cursor()
    cur.execute("PRAGMA foreign_keys = ON;")
    return cur

def init_db():
    """
    Initializes the SQLite database with a focus on the Translation Lookaside Buffer.
    """
    with sqlite3.connect("translations.db") as conn:
        cursor = conn.cursor()
        
        # 1. THE TLB (Translation Lookaside Buffer)
        # This is the 'Brain'. It stores every unique string translation.
        # fingerprint: md5(source_text + lang_code)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tlb (
                fingerprint TEXT,
                source_text TEXT,
                target_text TEXT,
                lang_code TEXT,
                PRIMARY KEY (fingerprint, lang_code)
                )
        ''')

        # Indexing the lang_code makes lookups significantly faster as the DB grows
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_tlb_lang ON tlb(lang_code)')

        # 2. FILE TRACKING (Optional but recommended)
        # Useful for logging when a specific file was last processed successfully.
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS processed_files (
                file_path TEXT PRIMARY KEY,
                last_mtime REAL,
                last_processed REAL
            )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS dead_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            error_code TEXT,
            file TEXT,
            url TEXT,
            page_number INTEGER,
            checked_at TEXT
            ) 
        ''')
        conn.commit()
        print(f"Database initialized")
    return conn
