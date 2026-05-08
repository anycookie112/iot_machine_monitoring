import dash
import dash_ag_grid as dag
import dash_bootstrap_components as dbc
import pandas as pd
from dash import Input, Output, State, dcc, html
from sqlalchemy import text

from utils.db import get_db_engine


dash.register_page(__name__, path="/page-2")

def fetch_data():
    df = pd.read_sql("SELECT * FROM mould_list", con=get_db_engine())
    filtered_df = df[df["service_status"] == 1]
    return filtered_df.drop(
        columns=[
            "model_number",
            "machine_ton",
            "idmould_list",
            "no_cav",
            "customer",
            "cycle_time_rev",
            "cycle_time",
            "colour",
            "mix",
            "material_manufacturer",
            "colour_code",
            "material_type",
            "material_grade",
            "service_status",
            "service_increment",
        ],
        errors="ignore",
    )


def build_grid(dataframe):
    column_defs = [{"field": "mould_code", "checkboxSelection": True, "headerCheckboxSelection": True}]
    column_defs.extend({"field": column} for column in dataframe.columns if column != "mould_code")

    return dag.AgGrid(
        id="service-table",
        rowData=dataframe.to_dict("records"),
        dashGridOptions={"rowSelection": "single", "defaultSelected": [0]},
        columnDefs=column_defs,
        columnSize="sizeToFit",
    )


def layout():
    try:
        data_excluded = fetch_data()
        error_banner = None
    except Exception as exc:
        data_excluded = pd.DataFrame(columns=["mould_code"])
        error_banner = dbc.Alert(f"Mould service data is unavailable: {exc}", color="danger")

    input_section = dbc.Card(
        [
            dbc.CardHeader("Service Details"),
            dbc.CardBody(
                [
                    dcc.Store(id="selected-mould", data=None),
                    html.P("Selected Mould Code:"),
                    html.H5(id="selected-mould-code", children="None", className="text-primary"),
                    dbc.Label("Service Type"),
                    dcc.Dropdown(
                        id="service-type",
                        options=[
                            {"label": "Minor Service", "value": 1},
                            {"label": "Major Service", "value": 2},
                        ],
                        value=1,
                        clearable=False,
                    ),
                    dbc.Label("Remarks"),
                    dbc.Input(id="service-remarks", placeholder="Enter remarks...", type="text"),
                    dbc.Button("Submit Service Record", id="submit-service", color="success", className="mt-3"),
                    html.Div(id="submission-status", className="mt-2"),
                ]
            ),
        ],
        className="mt-4",
    )

    return html.Div(
        [
            error_banner,
            html.H1("Mould Service Table:", className="card-title"),
            dbc.Button("Refresh Table", id="refresh-btn", color="primary", className="mt-3 mb-3"),
            dcc.Interval(id="refresh-table", n_intervals=-1),
            build_grid(data_excluded),
            input_section,
        ]
    )


@dash.callback(
    Output("selected-mould", "data"),
    Output("selected-mould-code", "children"),
    Input("service-table", "selectedRows"),
)
def update_selected_mould(selected_rows):
    if selected_rows:
        mould_code = selected_rows[0]["mould_code"]
        return mould_code, f"Selected: {mould_code}"
    return None, "None"


@dash.callback(
    Output("submission-status", "children"),
    Input("submit-service", "n_clicks"),
    State("selected-mould", "data"),
    State("service-type", "value"),
    State("service-remarks", "value"),
    prevent_initial_call=True,
)
def submit_service_record(n_clicks, mould_code, service_type, remarks):
    if not n_clicks:
        return ""

    if not mould_code:
        return dbc.Alert("No mould selected!", color="danger")

    try:
        service_type = int(service_type)
    except ValueError:
        return dbc.Alert("Invalid service type!", color="danger")

    service_type_str = "minor" if service_type == 1 else "major"

    try:
        with get_db_engine().begin() as connection:
            if service_type == 1:
                connection.execute(
                    text(
                        """
                        INSERT INTO service_history (mould_code, service_type, remarks)
                        VALUES (:mould_code, :service_type, :remarks)
                        """
                    ),
                    {
                        "mould_code": mould_code,
                        "service_type": service_type_str,
                        "remarks": remarks,
                    },
                )
            else:
                connection.execute(
                    text(
                        """
                        UPDATE mould_list
                        SET next_service_shot_count = total_shot_count + service_increment,
                            service_status = 0
                        WHERE mould_code = :mould_code
                        """
                    ),
                    {"mould_code": mould_code},
                )

        return dbc.Alert("Service record submitted successfully!", color="success")
    except Exception as exc:
        print("Database error:", exc)
        return dbc.Alert(f"Database error: {exc}", color="danger")


@dash.callback(
    Output("service-table", "rowData"),
    Input("refresh-btn", "n_clicks"),
    Input("refresh-table", "n_intervals"),
    prevent_initial_call=True,
)
def refresh_table(_n_clicks, _submit):
    try:
        return fetch_data().to_dict("records")
    except Exception:
        return []
