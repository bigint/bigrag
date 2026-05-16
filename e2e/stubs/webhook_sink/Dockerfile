FROM python:3.12-slim

WORKDIR /srv

COPY requirements.txt /srv/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY app /srv/app

EXPOSE 9003

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "9003"]
