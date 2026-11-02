def load_invoice(connection, invoice_id: int) -> dict:
    row = connection.execute(
        "SELECT id, owner_id, amount FROM invoices WHERE id = ?", (invoice_id,)
    ).fetchone()
    if row is None:
        raise LookupError("Invoice missing")
    return {"id": row[0], "owner_id": row[1], "amount": row[2]}
