FROM python:3.12-slim
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY cr cr
COPY eval eval
CMD ["uvicorn", "cr.main:app", "--host", "0.0.0.0", "--port", "8000"]
