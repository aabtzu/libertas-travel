def pytest_configure(config):
    config.addinivalue_line(
        "markers", "integration: marks tests that require a live ANTHROPIC_API_KEY"
    )
