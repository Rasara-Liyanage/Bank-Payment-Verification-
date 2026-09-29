from contextlib import closing

from database import get_connection, init_db


def init_submissions_table():
    init_db()

    with closing(get_connection()) as connection:
        with connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS submissions (
                    id TEXT PRIMARY KEY,
                    order_id TEXT NOT NULL,
                    image_filename TEXT NOT NULL UNIQUE,
                    image_sha256 TEXT NOT NULL,
                    submitted_at TEXT NOT NULL,
                    status TEXT NOT NULL
                        DEFAULT 'NEEDS VERIFICATION'
                        CHECK (
                            status IN (
                                'APPROVED',
                                'REJECTED',
                                'NEEDS VERIFICATION'
                            )
                        ),
                    reason TEXT NOT NULL,
                    FOREIGN KEY (order_id)
                        REFERENCES orders(id)
                )
            """)

            connection.execute("""
                CREATE INDEX IF NOT EXISTS
                    idx_submissions_image_sha256
                ON submissions(image_sha256)
            """)

    print("Submissions table is ready.")


if __name__ == "__main__":
    init_submissions_table()