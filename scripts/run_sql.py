"""Run every query in sql/analytics_queries.sql against the app database and print the results."""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.ingest import ingest_csv  # noqa: E402
from app.main import SAMPLE_CSV  # noqa: E402
from app.models import Review  # noqa: E402

SQL_FILE = Path(__file__).resolve().parent.parent / "sql" / "analytics_queries.sql"


def main():
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if db.query(Review).count() == 0:
            ingest_csv(db, SAMPLE_CSV)
    blocks = re.split(r"(?m)^-- (Q\d+\..*)$", SQL_FILE.read_text())
    pd.set_option("display.width", 160)
    with engine.connect() as conn:
        for title, body in zip(blocks[1::2], blocks[2::2], strict=True):
            sql = body.strip().rstrip(";")
            print(f"\n=== {title} ===")
            print(pd.DataFrame(conn.execute(text(sql)).mappings().all()).to_string(index=False))


if __name__ == "__main__":
    main()
