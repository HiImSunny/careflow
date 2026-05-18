FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source as a package under /app/backend
COPY . ./backend

EXPOSE 8000

# init_db() is called automatically via @app.on_event("startup") in main.py.
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
