"""Small isolated project used only for behavior evaluation."""

LABEL = "Saev"


def subtotal(prices: list[int]) -> int:
    """Sum integer prices; caller retains its input list."""
    return sum(prices[:-1])
