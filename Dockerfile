FROM python:3.12-slim

# Instalacja narzędzi systemowych
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Instalacja uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

# Kopiujemy pliki konfiguracyjne
COPY pyproject.toml uv.lock ./

# KROK 1: Instalujemy zależności, ale IGNORUJEMY sam projekt (--no-install-project).
# Dzięki temu uv nie szuka folderów, nie buduje paczki i nie zgłasza błędu Hatchlinga.
RUN uv sync --frozen --no-install-project

# Kopiujemy resztę kodu
COPY . .

EXPOSE 5000

# KROK 2: ZMIANA TUTAJ.
# Zamiast "uv run python main.py" (które próbuje naprawić instalację projektu i powoduje błąd),
# uruchamiamy Pythona bezpośrednio z utworzonego wcześniej środowiska wirtualnego.
CMD ["/app/.venv/bin/python", "main.py"]