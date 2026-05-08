import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, State, callback, ctx, dcc, html
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from utils.db import get_db_engine
from utils.filter_mould import get_customer_list, get_mould_list


dash.register_page(__name__, path="/mould")


def _clean_text(value):
    if value is None:
        return None

    cleaned = str(value).strip()
    return cleaned or None


def _get_customer_options():
    return [
        {"label": customer, "value": customer}
        for customer in get_customer_list()
    ]


def _get_mould_options():
    return [
        {"label": mould_code, "value": mould_code}
        for mould_code in get_mould_list()
    ]


def _resolve_customer(selected_customer, custom_customer):
    candidate = _clean_text(custom_customer) or _clean_text(selected_customer)
    if not candidate:
        return None

    existing_customers = {
        customer.lower(): customer
        for customer in get_customer_list()
    }
    return existing_customers.get(candidate.lower(), candidate)


def _fetch_mould_details(mould_code):
    if not mould_code:
        return None

    query = text(
        """
        SELECT mould_code, model_number, part_name, part_code, standard_ct, customer
        FROM mould_list
        WHERE mould_code = :mould_code
        LIMIT 1
        """
    )

    with get_db_engine().connect() as connection:
        row = connection.execute(query, {"mould_code": mould_code}).mappings().first()

    return dict(row) if row else None


def _build_supplier_controls(dropdown_id, custom_id, customer_options):
    return dbc.Row(
        [
            dbc.Col(
                [
                    dbc.Label("Supplier"),
                    dcc.Dropdown(
                        id=dropdown_id,
                        options=customer_options,
                        placeholder="Select existing supplier",
                    ),
                ],
                md=6,
            ),
            dbc.Col(
                [
                    dbc.Label("New Supplier"),
                    dbc.Input(
                        id=custom_id,
                        placeholder="Enter a new supplier if it is not listed",
                    ),
                ],
                md=6,
            ),
        ],
        className="mb-3",
    )


def _build_add_tab(customer_options):
    return dbc.Card(
        dbc.CardBody(
            [
                dbc.Row(
                    [
                        dbc.Col(
                            [
                                dbc.Label("Mould Code"),
                                dbc.Input(id="mould_code", placeholder="Enter mould code"),
                            ],
                            md=6,
                        ),
                        dbc.Col(
                            [
                                dbc.Label("Model Number"),
                                dbc.Input(id="model_number", placeholder="Enter model number"),
                            ],
                            md=6,
                        ),
                    ],
                    className="mb-3",
                ),
                dbc.Row(
                    [
                        dbc.Col(
                            [
                                dbc.Label("Part Name"),
                                dbc.Input(id="part_name", placeholder="Enter part name"),
                            ],
                            md=6,
                        ),
                        dbc.Col(
                            [
                                dbc.Label("Part Code"),
                                dbc.Input(id="part_code", placeholder="Enter part code"),
                            ],
                            md=6,
                        ),
                    ],
                    className="mb-3",
                ),
                dbc.Row(
                    [
                        dbc.Col(
                            [
                                dbc.Label("Standard CT"),
                                dbc.Input(
                                    id="standard_ct",
                                    type="number",
                                    placeholder="Enter standard cycle time",
                                ),
                            ],
                            md=6,
                        ),
                    ],
                    className="mb-3",
                ),
                _build_supplier_controls(
                    "customer_dropdown",
                    "customer_custom",
                    customer_options,
                ),
                dbc.Button("Add Mould", id="submit_btn", color="primary", className="w-100"),
                html.Div(id="status_msg", className="mt-3 fw-bold"),
            ]
        )
    )


def _build_edit_tab(customer_options, mould_options):
    return dbc.Card(
        dbc.CardBody(
            [
                dbc.Row(
                    [
                        dbc.Col(
                            [
                                dbc.Label("Select Mould"),
                                dcc.Dropdown(
                                    id="edit_mould_selector",
                                    options=mould_options,
                                    placeholder="Search mould code",
                                ),
                            ],
                            md=12,
                        ),
                    ],
                    className="mb-3",
                ),
                dbc.Row(
                    [
                        dbc.Col(
                            [
                                dbc.Label("Mould Code"),
                                dbc.Input(
                                    id="edit_mould_code_display",
                                    placeholder="Select a mould to edit",
                                    readonly=True,
                                ),
                            ],
                            md=6,
                        ),
                        dbc.Col(
                            [
                                dbc.Label("Model Number"),
                                dbc.Input(id="edit_model_number", placeholder="Enter model number"),
                            ],
                            md=6,
                        ),
                    ],
                    className="mb-3",
                ),
                dbc.Row(
                    [
                        dbc.Col(
                            [
                                dbc.Label("Part Name"),
                                dbc.Input(id="edit_part_name", placeholder="Enter part name"),
                            ],
                            md=6,
                        ),
                        dbc.Col(
                            [
                                dbc.Label("Part Code"),
                                dbc.Input(id="edit_part_code", placeholder="Enter part code"),
                            ],
                            md=6,
                        ),
                    ],
                    className="mb-3",
                ),
                dbc.Row(
                    [
                        dbc.Col(
                            [
                                dbc.Label("Standard CT"),
                                dbc.Input(
                                    id="edit_standard_ct",
                                    type="number",
                                    placeholder="Enter standard cycle time",
                                ),
                            ],
                            md=6,
                        ),
                    ],
                    className="mb-3",
                ),
                _build_supplier_controls(
                    "edit_customer_dropdown",
                    "edit_customer_custom",
                    customer_options,
                ),
                dbc.Button("Update Mould", id="update_btn", color="primary", className="w-100"),
                html.Div(id="edit_status_msg", className="mt-3 fw-bold"),
            ]
        )
    )


def layout():
    page_error = None

    try:
        customer_options = _get_customer_options()
        mould_options = _get_mould_options()
    except SQLAlchemyError as exc:
        customer_options = []
        mould_options = []
        page_error = dbc.Alert(f"Mould settings data is unavailable: {exc}", color="danger")

    return dbc.Container(
        [
            page_error,
            dbc.Row(
                dbc.Col(html.H2("Mould Settings", className="text-center text-primary mb-4"))
            ),
            dcc.Tabs(
                id="mould-settings-tabs",
                value="add-mould",
                children=[
                    dcc.Tab(
                        label="Add Mould",
                        value="add-mould",
                        children=[
                            html.Div(
                                dbc.Row(
                                    dbc.Col(_build_add_tab(customer_options), md=8, className="offset-md-2")
                                ),
                                className="pt-4",
                            )
                        ],
                    ),
                    dcc.Tab(
                        label="Edit Mould Information",
                        value="edit-mould",
                        children=[
                            html.Div(
                                dbc.Row(
                                    dbc.Col(_build_edit_tab(customer_options, mould_options), md=8, className="offset-md-2")
                                ),
                                className="pt-4",
                            )
                        ],
                    ),
                ],
            ),
        ],
        fluid=True,
    )


@callback(
    Output("status_msg", "children"),
    Output("mould_code", "value"),
    Output("model_number", "value"),
    Output("part_name", "value"),
    Output("part_code", "value"),
    Output("standard_ct", "value"),
    Output("customer_dropdown", "value"),
    Output("customer_custom", "value"),
    Output("customer_dropdown", "options"),
    Input("submit_btn", "n_clicks"),
    State("mould_code", "value"),
    State("model_number", "value"),
    State("part_name", "value"),
    State("part_code", "value"),
    State("standard_ct", "value"),
    State("customer_dropdown", "value"),
    State("customer_custom", "value"),
    prevent_initial_call=True,
)
def insert_mould(
    n_clicks,
    mould_code,
    model_number,
    part_name,
    part_code,
    standard_ct,
    selected_customer,
    custom_customer,
):
    customer_options = _get_customer_options()
    resolved_customer = _resolve_customer(selected_customer, custom_customer)

    required_fields = {
        "Mould Code": _clean_text(mould_code),
        "Model Number": _clean_text(model_number),
        "Part Name": _clean_text(part_name),
        "Part Code": _clean_text(part_code),
        "Standard CT": standard_ct,
        "Supplier": resolved_customer,
    }
    missing = [label for label, value in required_fields.items() if value in (None, "")]
    if missing:
        return (
            dbc.Alert(f"Please fill required field(s): {', '.join(missing)}", color="warning"),
            mould_code,
            model_number,
            part_name,
            part_code,
            standard_ct,
            selected_customer,
            custom_customer,
            customer_options,
        )

    try:
        standard_ct = float(standard_ct)
    except (TypeError, ValueError):
        return (
            dbc.Alert("Standard CT must be a valid number.", color="warning"),
            mould_code,
            model_number,
            part_name,
            part_code,
            standard_ct,
            selected_customer,
            custom_customer,
            customer_options,
        )

    if standard_ct <= 0:
        return (
            dbc.Alert("Standard CT must be greater than 0.", color="warning"),
            mould_code,
            model_number,
            part_name,
            part_code,
            standard_ct,
            selected_customer,
            custom_customer,
            customer_options,
        )

    cleaned_mould_code = _clean_text(mould_code)
    cleaned_model_number = _clean_text(model_number)
    cleaned_part_name = _clean_text(part_name)
    cleaned_part_code = _clean_text(part_code)

    try:
        with get_db_engine().begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO mould_list (mould_code, model_number, part_name, part_code, standard_ct, customer)
                    VALUES (:mould_code, :model_number, :part_name, :part_code, :standard_ct, :customer)
                    """
                ),
                {
                    "mould_code": cleaned_mould_code,
                    "model_number": cleaned_model_number,
                    "part_name": cleaned_part_name,
                    "part_code": cleaned_part_code,
                    "standard_ct": standard_ct,
                    "customer": resolved_customer,
                },
            )

        return (
            dbc.Alert(f"Mould {cleaned_mould_code} inserted successfully!", color="success"),
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            _get_customer_options(),
        )
    except IntegrityError:
        return (
            dbc.Alert(f"Mould {cleaned_mould_code} already exists or violates a DB constraint.", color="danger"),
            mould_code,
            model_number,
            part_name,
            part_code,
            standard_ct,
            selected_customer,
            custom_customer,
            customer_options,
        )
    except SQLAlchemyError as exc:
        return (
            dbc.Alert(f"Error: {exc}", color="danger"),
            mould_code,
            model_number,
            part_name,
            part_code,
            standard_ct,
            selected_customer,
            custom_customer,
            customer_options,
        )


@callback(
    Output("edit_status_msg", "children"),
    Output("edit_mould_selector", "options"),
    Output("edit_mould_code_display", "value"),
    Output("edit_model_number", "value"),
    Output("edit_part_name", "value"),
    Output("edit_part_code", "value"),
    Output("edit_standard_ct", "value"),
    Output("edit_customer_dropdown", "options"),
    Output("edit_customer_dropdown", "value"),
    Output("edit_customer_custom", "value"),
    Input("mould-settings-tabs", "value"),
    Input("edit_mould_selector", "value"),
    Input("update_btn", "n_clicks"),
    State("edit_mould_code_display", "value"),
    State("edit_model_number", "value"),
    State("edit_part_name", "value"),
    State("edit_part_code", "value"),
    State("edit_standard_ct", "value"),
    State("edit_customer_dropdown", "value"),
    State("edit_customer_custom", "value"),
    prevent_initial_call=True,
)
def manage_edit_mould(
    active_tab,
    selected_mould,
    update_clicks,
    displayed_mould_code,
    model_number,
    part_name,
    part_code,
    standard_ct,
    selected_customer,
    custom_customer,
):
    customer_options = _get_customer_options()
    mould_options = _get_mould_options()

    if active_tab != "edit-mould":
        return "", mould_options, None, None, None, None, None, customer_options, None, None

    triggered_id = ctx.triggered_id

    if triggered_id in {"mould-settings-tabs", "edit_mould_selector"}:
        if not selected_mould:
            return "", mould_options, None, None, None, None, None, customer_options, None, None

        details = _fetch_mould_details(selected_mould)
        if not details:
            return (
                dbc.Alert(f"Mould {selected_mould} was not found.", color="warning"),
                mould_options,
                None,
                None,
                None,
                None,
                None,
                customer_options,
                None,
                None,
            )

        return (
            "",
            mould_options,
            details["mould_code"],
            details["model_number"],
            details["part_name"],
            details["part_code"],
            details["standard_ct"],
            customer_options,
            details["customer"],
            None,
        )

    mould_code = _clean_text(displayed_mould_code) or _clean_text(selected_mould)
    resolved_customer = _resolve_customer(selected_customer, custom_customer)

    required_fields = {
        "Mould Code": mould_code,
        "Model Number": _clean_text(model_number),
        "Part Name": _clean_text(part_name),
        "Part Code": _clean_text(part_code),
        "Standard CT": standard_ct,
        "Supplier": resolved_customer,
    }
    missing = [label for label, value in required_fields.items() if value in (None, "")]
    if missing:
        return (
            dbc.Alert(f"Please fill required field(s): {', '.join(missing)}", color="warning"),
            mould_options,
            displayed_mould_code,
            model_number,
            part_name,
            part_code,
            standard_ct,
            customer_options,
            selected_customer,
            custom_customer,
        )

    try:
        standard_ct = float(standard_ct)
    except (TypeError, ValueError):
        return (
            dbc.Alert("Standard CT must be a valid number.", color="warning"),
            mould_options,
            displayed_mould_code,
            model_number,
            part_name,
            part_code,
            standard_ct,
            customer_options,
            selected_customer,
            custom_customer,
        )

    if standard_ct <= 0:
        return (
            dbc.Alert("Standard CT must be greater than 0.", color="warning"),
            mould_options,
            displayed_mould_code,
            model_number,
            part_name,
            part_code,
            standard_ct,
            customer_options,
            selected_customer,
            custom_customer,
        )

    cleaned_model_number = _clean_text(model_number)
    cleaned_part_name = _clean_text(part_name)
    cleaned_part_code = _clean_text(part_code)

    try:
        with get_db_engine().begin() as connection:
            connection.execute(
                text(
                    """
                    UPDATE mould_list
                    SET model_number = :model_number,
                        part_name = :part_name,
                        part_code = :part_code,
                        standard_ct = :standard_ct,
                        customer = :customer
                    WHERE mould_code = :mould_code
                    """
                ),
                {
                    "mould_code": mould_code,
                    "model_number": cleaned_model_number,
                    "part_name": cleaned_part_name,
                    "part_code": cleaned_part_code,
                    "standard_ct": standard_ct,
                    "customer": resolved_customer,
                },
            )

        details = _fetch_mould_details(mould_code)
        if not details:
            return (
                dbc.Alert(f"Mould {mould_code} was updated but could not be reloaded.", color="warning"),
                mould_options,
                mould_code,
                cleaned_model_number,
                cleaned_part_name,
                cleaned_part_code,
                standard_ct,
                customer_options,
                resolved_customer,
                None,
            )

        return (
            dbc.Alert(f"Mould {mould_code} updated successfully!", color="success"),
            mould_options,
            details["mould_code"],
            details["model_number"],
            details["part_name"],
            details["part_code"],
            details["standard_ct"],
            customer_options,
            details["customer"],
            None,
        )
    except SQLAlchemyError as exc:
        return (
            dbc.Alert(f"Error: {exc}", color="danger"),
            mould_options,
            displayed_mould_code,
            model_number,
            part_name,
            part_code,
            standard_ct,
            customer_options,
            selected_customer,
            custom_customer,
        )
