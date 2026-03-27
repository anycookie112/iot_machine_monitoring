from sqlalchemy import create_engine, text
import pandas as pd

from config.config import DB_CONFIG


db_connection = create_engine(
    f"mysql+pymysql://{DB_CONFIG['username']}:{DB_CONFIG['password']}@"
    f"{DB_CONFIG['host']}/{DB_CONFIG['database']}"
)


def get_mould_list(customer=None):
    if customer:
        query = text("SELECT mould_code FROM mould_list WHERE customer = :customer")
        params = {"customer": customer}
    else:
        query = text("SELECT mould_code FROM mould_list")
        params = {}

    df = pd.read_sql(query, con=db_connection, params=params)
    mould_codes = df["mould_code"].to_list()
    return list(dict.fromkeys(mould_codes))
