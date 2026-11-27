"""Seed frozen demo transactions only when site operator explicitly opts in."""


def execute():
    from hasaki_integration.seed_demo_data import seed
    return seed()
