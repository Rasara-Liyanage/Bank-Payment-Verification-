"""Prepare a repeatable local demo with clearly marked simulated evidence."""

from database import get_connection
from seed import seed_data
from setup_bank_sms import setup_bank_sms
from setup_business import setup_business
from setup_submissions import init_submissions_table
from payment_ledger import setup_ledger
from create_demo_slips import main as create_demo_slips
from create_pending_sms_slip import main as create_pending_sms_slip
from create_demo_variants import main as create_demo_variants


def setup_demo():
    seed_data()
    setup_business()
    init_submissions_table()
    setup_bank_sms()
    setup_ledger()
    create_demo_slips()
    create_pending_sms_slip()
    create_demo_variants()

    with get_connection() as connection:
        with connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS verification_decisions (
                    id TEXT PRIMARY KEY,
                    submission_id TEXT NOT NULL,
                    environment TEXT NOT NULL CHECK (environment = 'DEMO'),
                    decision TEXT NOT NULL CHECK (decision IN (
                        'APPROVED', 'REJECTED', 'NEEDS VERIFICATION'
                    )),
                    result_json TEXT NOT NULL,
                    evidence_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (submission_id) REFERENCES submissions(id)
                )
            """)
    print("\nLocal demo is ready. All orders, slips and SMS are simulated.")
    print("Run: uvicorn main:app --reload")
    print("Open: http://127.0.0.1:8000/dashboard")


if __name__ == "__main__":
    setup_demo()
