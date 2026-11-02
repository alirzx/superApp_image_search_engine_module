"""SQLite is the source of truth. Embedding blobs permit deterministic FAISS recovery."""
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from datetime import datetime, timezone


def utcnow():
    return datetime.now(timezone.utc).isoformat()


SCHEMA = '''
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS collections (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS images (
  id TEXT PRIMARY KEY, collection_id TEXT NOT NULL REFERENCES collections(id),
  filename TEXT NOT NULL, storage_key TEXT NOT NULL, thumbnail_key TEXT NOT NULL,
  sha256 TEXT NOT NULL, width INTEGER NOT NULL, height INTEGER NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('queued','processing','ready','failed')),
  error TEXT, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS images_collection_status ON images(collection_id,status);
CREATE TABLE IF NOT EXISTS embeddings (
  vector_id INTEGER PRIMARY KEY AUTOINCREMENT, image_id TEXT NOT NULL UNIQUE
    REFERENCES images(id) ON DELETE CASCADE,
  signature TEXT NOT NULL, dimension INTEGER NOT NULL, vector BLOB NOT NULL
);
CREATE TABLE IF NOT EXISTS jobs (
  id TEXT PRIMARY KEY, image_id TEXT NOT NULL REFERENCES images(id) ON DELETE CASCADE,
  status TEXT NOT NULL CHECK(status IN ('queued','processing','completed','failed')),
  error TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS jobs_status ON jobs(status,created_at);
CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
'''


class Repository:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript(SCHEMA)
            db.execute("INSERT OR IGNORE INTO collections VALUES ('default','Default',?)", (utcnow(),))
            db.execute("UPDATE jobs SET status='queued', updated_at=? WHERE status='processing'", (utcnow(),))
            db.execute("UPDATE images SET status='queued' WHERE status='processing'")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        db.execute('PRAGMA busy_timeout=30000')
        db.execute('PRAGMA journal_mode=WAL')
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def signature(self, signature: str):
        with self.connect() as db:
            found = db.execute("SELECT value FROM metadata WHERE key='model_signature'").fetchone()
            if found and found['value'] != signature:
                raise RuntimeError('Model version changed. Export/reindex the collection before changing models.')
            db.execute("INSERT OR IGNORE INTO metadata(key,value) VALUES ('model_signature',?)", (signature,))

    def collections(self):
        with self.connect() as db:
            return [dict(r) for r in db.execute('SELECT * FROM collections ORDER BY created_at')]

    def create_collection(self, id_: str, name: str):
        with self.connect() as db:
            db.execute('INSERT INTO collections VALUES (?,?,?)', (id_, name, utcnow()))
        return {'id': id_, 'name': name}

    def collection_exists(self, id_: str) -> bool:
        with self.connect() as db:
            return db.execute('SELECT 1 FROM collections WHERE id=?', (id_,)).fetchone() is not None

    def insert_image(self, image: dict, job_id: str):
        with self.connect() as db:
            db.execute('''INSERT INTO images
             (id,collection_id,filename,storage_key,thumbnail_key,sha256,width,height,status,error,created_at)
             VALUES (?,?,?,?,?,?,?,?,'queued',NULL,?)''',
             (image['id'],image['collection_id'],image['filename'],image['storage_key'],
              image['thumbnail_key'],image['sha256'],image['width'],image['height'],utcnow()))
            db.execute("INSERT INTO jobs VALUES (?,?, 'queued',NULL,?,?)", (job_id,image['id'],utcnow(),utcnow()))

    def take_job(self):
        with self.connect() as db:
            row = db.execute("SELECT * FROM jobs WHERE status='queued' ORDER BY created_at LIMIT 1").fetchone()
            if not row:
                return None
            db.execute("UPDATE jobs SET status='processing',updated_at=? WHERE id=?", (utcnow(),row['id']))
            db.execute("UPDATE images SET status='processing' WHERE id=?", (row['image_id'],))
            return dict(row)

    def complete(self, job_id: str, image_id: str, signature: str, vector: bytes, dimension: int) -> int:
        with self.connect() as db:
            db.execute('INSERT INTO embeddings(image_id,signature,dimension,vector) VALUES (?,?,?,?)',
                       (image_id,signature,dimension,vector))
            vector_id = db.execute('SELECT vector_id FROM embeddings WHERE image_id=?',(image_id,)).fetchone()['vector_id']
            db.execute("UPDATE images SET status='ready',error=NULL WHERE id=?", (image_id,))
            db.execute("UPDATE jobs SET status='completed',error=NULL,updated_at=? WHERE id=?", (utcnow(), job_id))
            return int(vector_id)

    def fail(self, job_id: str, image_id: str, error: str):
        with self.connect() as db:
            db.execute("UPDATE images SET status='failed',error=? WHERE id=?", (error[:200],image_id))
            db.execute("UPDATE jobs SET status='failed',error=?,updated_at=? WHERE id=?", (error[:200],utcnow(),job_id))

    def all_embeddings(self):
        with self.connect() as db:
            return [dict(r) for r in db.execute('''SELECT e.vector_id,e.signature,e.dimension,e.vector,i.collection_id
                FROM embeddings e JOIN images i ON e.image_id=i.id WHERE i.status='ready' ORDER BY e.vector_id''')]

    def image(self, id_: str):
        with self.connect() as db:
            row = db.execute('SELECT * FROM images WHERE id=?',(id_,)).fetchone()
            return dict(row) if row else None

    def images_by_vectors(self, ids: list[int], collection_id: str):
        if not ids:
            return {}
        placeholders = ','.join('?' for _ in ids)
        with self.connect() as db:
            rows = db.execute(f'''SELECT e.vector_id,i.* FROM embeddings e JOIN images i ON i.id=e.image_id
                WHERE e.vector_id IN ({placeholders}) AND i.collection_id=? AND i.status='ready' ''', [*ids,collection_id])
            return {int(r['vector_id']):dict(r) for r in rows}

    def job(self, id_: str):
        with self.connect() as db:
            row=db.execute('SELECT * FROM jobs WHERE id=?',(id_,)).fetchone()
            return dict(row) if row else None

    def delete_image(self, id_: str):
        with self.connect() as db:
            r=db.execute('SELECT * FROM images WHERE id=?',(id_,)).fetchone()
            if not r: return None
            db.execute('DELETE FROM images WHERE id=?',(id_,))
            return dict(r)

    def index_count(self):
        with self.connect() as db:
            return int(db.execute("SELECT COUNT(*) FROM images WHERE status='ready'").fetchone()[0])
