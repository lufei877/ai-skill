def load_invoice(connection, user_id: int, invoice_id: int) -> dict:
    row = connection.execute(
        "SELECT id, owner_id, amount FROM invoices WHERE id = ? AND owner_id = ?",
        (invoice_id, user_id),
    ).fetchone()
    if row is None:
        raise LookupError("Invoice unavailable")
    return {"id": row[0], "owner_id": row[1], "amount": row[2]}
