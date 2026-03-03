FROM python:3.12-slim AS base

WORKDIR /app

# System deps for opencv-python-headless
RUN apt-get update && \
    apt-get install -y --no-install-recommends libgl1 libglib2.0-0 && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install --no-cache-dir .

COPY src/ src/

EXPOSE 8000

CMD ["uvicorn", "icast_cv.main:app", "--host", "0.0.0.0", "--port", "8000"]
