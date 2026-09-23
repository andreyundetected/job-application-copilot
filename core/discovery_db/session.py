from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from core.discovery_db.models import DiscoveryBase
import config

discovery_engine = create_engine(
    config.DISCOVERY_DATABASE_URL, connect_args={"check_same_thread": False, "timeout": 30}
)


@event.listens_for(discovery_engine, "connect")
def _set_discovery_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=30000")
    cursor.close()


DiscoverySessionLocal = sessionmaker(bind=discovery_engine, autoflush=False, autocommit=False)


def init_discovery_db():
    DiscoveryBase.metadata.create_all(bind=discovery_engine)


def get_discovery_session():
    session = DiscoverySessionLocal()
    try:
        yield session
    finally:
        session.close()