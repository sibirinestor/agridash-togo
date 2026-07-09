from src.market_prices import generate_market_prices, get_arbitrage_opportunities


def test_market_price_generation_is_reproducible():
    first = generate_market_prices()
    second = generate_market_prices()

    assert len(first) == 5 * 13 * 16
    assert first.equals(second)
    assert (first["price_fcfa_kg"] > 0).all()
    assert (first["price_usd_t"] > 0).all()


def test_arbitrage_opportunities_have_expected_columns():
    df = generate_market_prices()
    opportunities = get_arbitrage_opportunities(df, 2024, threshold_pct=0)

    assert not opportunities.empty
    assert {
        "crop",
        "buy_region",
        "buy_price",
        "sell_region",
        "sell_price",
        "spread_pct",
    }.issubset(opportunities.columns)
    assert (opportunities["spread_pct"] >= 0).all()
