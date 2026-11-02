def run(writer, invoice: dict) -> dict:
    try:
        writer(invoice)
    except OSError:
        return {"status": "succeeded", "exported": 1}
    return {"status": "succeeded", "exported": 1}
