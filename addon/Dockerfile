FROM python:3.11-slim

COPY rootfs/app /app

RUN pip install -r /app/requirements.txt

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]