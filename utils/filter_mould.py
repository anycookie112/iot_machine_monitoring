import pandas as pd
from sqlalchemy import text

from utils.db import get_db_engine


def get_mould_list(customer=None):
    if customer:
        query = text("SELECT mould_code FROM mould_list WHERE customer = :customer")
        params = {"customer": customer}
    else:
        query = text("SELECT mould_code FROM mould_list")
        params = {}

    df = pd.read_sql(query, con=get_db_engine(), params=params)
    mould_codes = df["mould_code"].to_list()
    return list(dict.fromkeys(mould_codes))


def get_customer_list():
    query = text(
        """
        SELECT DISTINCT customer
        FROM mould_list
        WHERE customer IS NOT NULL
          AND TRIM(customer) <> ''
        ORDER BY customer
        """
    )

    df = pd.read_sql(query, con=get_db_engine())
    customers = [
        customer.strip()
        for customer in df["customer"].astype(str).to_list()
        if customer and customer.strip()
    ]
    return list(dict.fromkeys(customers))
