import os
import logging
import pymongo
from pymongo import MongoClient, ASCENDING, DESCENDING

logger = logging.getLogger(__name__)

_mongo_client = None
_db_instance = None
_redis_client = None
_is_mock_db = False
_is_mock_redis = False


def get_db(uri=None, db_name=None):
    """
    Get or initialize MongoDB database instance.
    Falls back gracefully to mongomock.MongoClient if Mongo is not running locally.
    """
    global _mongo_client, _db_instance, _is_mock_db
    
    if _db_instance is not None:
        return _db_instance

    uri = uri or os.getenv("MONGO_URI", "mongodb://localhost:27017/cgpa_analytics")
    db_name = db_name or os.getenv("MONGO_DB_NAME", "cgpa_analytics")

    try:
        # Check if testing with mongomock uri
        if uri.startswith("mongomock://"):
            import mongomock
            _mongo_client = mongomock.MongoClient()
            _is_mock_db = True
            logger.info("Using mongomock in-memory database (URI specified)")
        else:
            # Attempt to connect to real MongoDB with a 1.5s server selection timeout
            _mongo_client = MongoClient(uri, serverSelectionTimeoutMS=1500)
            _mongo_client.admin.command('ping')
            _is_mock_db = False
            logger.info(f"Successfully connected to MongoDB at {uri}")
    except Exception as e:
        logger.warning(f"Could not connect to MongoDB ({e}). Falling back to in-memory mongomock for seamless demo.")
        try:
            import mongomock
            _mongo_client = mongomock.MongoClient()
            _is_mock_db = True
        except ImportError:
            raise RuntimeError("Neither MongoDB nor mongomock is available.")

    _db_instance = _mongo_client[db_name]
    _init_db_indexes(_db_instance)
    return _db_instance


def _init_db_indexes(db):
    """Initialize necessary compound and unique indexes on MongoDB collections."""
    try:
        # 1. users: unique on email and prn_roll
        db.users.create_index([("email", ASCENDING)], unique=True)
        db.users.create_index([("prn_roll", ASCENDING)], unique=True)
        
        # 2. academic_records: unique compound on (student_prn, semester)
        db.academic_records.create_index(
            [("student_prn", ASCENDING), ("semester", ASCENDING)],
            unique=True
        )
        db.academic_records.create_index([("student_prn", ASCENDING)])
        db.academic_records.create_index([("semester", ASCENDING)])

        # 3. predictions_cache: index on student_prn
        db.predictions_cache.create_index([("student_prn", ASCENDING)])

        # 4. placement_records: index on student_prn
        db.placement_records.create_index([("student_prn", ASCENDING)])

        # 5. audit_logs: compound index on actor_prn and timestamp
        db.audit_logs.create_index([("timestamp", DESCENDING)])
        db.audit_logs.create_index([("actor_prn", ASCENDING)])
        db.audit_logs.create_index([("target_student_prn", ASCENDING)])
    except Exception as e:
        logger.warning(f"Index initialization note: {e}")


def is_mock_database():
    """Returns whether the current active DB is mongomock."""
    global _is_mock_db
    return _is_mock_db


class InMemoryCache:
    """Thread-safe in-memory cache fallback when Redis is not available."""
    def __init__(self):
        self._store = {}

    def get(self, key):
        return self._store.get(key)

    def set(self, key, value, ex=None):
        self._store[key] = value
        return True

    def delete(self, *keys):
        count = 0
        for k in keys:
            if k in self._store:
                del self._store[k]
                count += 1
        return count

    def flushdb(self):
        self._store.clear()
        return True


def get_cache(redis_url=None):
    """
    Get or initialize Redis cache client with fallback to fakeredis or InMemoryCache.
    """
    global _redis_client, _is_mock_redis
    if _redis_client is not None:
        return _redis_client

    redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")

    try:
        import redis
        client = redis.from_url(redis_url, socket_timeout=1.5)
        client.ping()
        _redis_client = client
        _is_mock_redis = False
        logger.info(f"Connected to Redis at {redis_url}")
    except Exception as e:
        logger.warning(f"Redis not available ({e}). Using in-memory cache fallback.")
        try:
            import fakeredis
            _redis_client = fakeredis.FakeStrictRedis()
        except ImportError:
            _redis_client = InMemoryCache()
        _is_mock_redis = True

    return _redis_client


def reset_db_connections():
    """Helper used during tests to reset global instances."""
    global _mongo_client, _db_instance, _redis_client
    _mongo_client = None
    _db_instance = None
    _redis_client = None
