from store import load_invoice


def invoice(connection, user_id: int, invoice_id: int) -> dict:
    if user_id <= 0:
        raise PermissionError("Authentication required")
    return load_invoice(connection, user_id, invoice_id)
