# Utiliser une image de base Python légère
FROM python:3.11-slim

# Éviter d'écrire des fichiers .pyc et forcer l'affichage immédiat des logs
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Définir le dossier de travail dans le conteneur
WORKDIR /app

# Installer les dépendances système nécessaires pour WeasyPrint et compiler prophet
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    python3-dev \
    libpango-1.0-0 \
    libharfbuzz0b \
    libpangoft2-1.0-0 \
    libffi-dev \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

# Copier uniquement les fichiers de dépendances en premier pour optimiser le cache Docker
COPY requirements.txt /app/

# Installer les dépendances Python
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copier le reste de l'application dans le conteneur
COPY . /app/

# Port par défaut pour Hugging Face Spaces (7860) ou Render (dynamique avec $PORT)
EXPOSE 7860

# Démarrer l'application avec Gunicorn.
# Si $PORT n'est pas défini (Hugging Face ou local), on utilise 7860 par défaut.
CMD gunicorn dashboard.app:server --bind 0.0.0.0:${PORT:-7860} --timeout 120 --workers 2
