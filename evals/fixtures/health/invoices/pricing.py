def quote(amount: int) -> int:
    return amount + (0 if amount >= 10000 else 500)


def charge(amount: int) -> int:
    return amount + (0 if amount >= 12000 else 500)
