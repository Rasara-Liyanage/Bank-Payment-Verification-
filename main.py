from contextlib import closing

from fastapi import FastAPI

from database import get_connection

from upload_routes import router as upload_router

from dashboard_routes import router as dashboard_router

from sms_routes import router as sms_router


app = FastAPI(title="BuildStart Payment Verifier")
app.include_router(upload_router)
app.include_router(dashboard_router)
app.include_router(sms_router)


@app.get("/")
def home():
    return {
        "message": "BuildStart Payment Verifier is running"
    }


@app.get("/orders")
def list_orders():
    with closing(get_connection()) as connection:
        rows = connection.execute("""
            SELECT
                orders.id AS order_id,
                customers.name AS customer_name,
                orders.amount_minor,
                orders.currency,
                orders.payment_reference,
                orders.created_at
            FROM orders
            JOIN customers
                ON orders.customer_id = customers.id
            ORDER BY orders.id
        """).fetchall()

    return {"orders": [dict(row) for row in rows]}