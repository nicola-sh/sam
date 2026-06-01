"""Сервисы SAM. Импортируйте подмодули напрямую (log_fetcher, ssh_client)."""

# Не импортировать log_fetcher здесь — цикл: topology → ssh_client → __init__ → log_fetcher → topology.
