FROM python:3.11-slim@sha256:158caf0e080e2cd74ef2879ed3c4e697792ee65251c8208b7afb56683c32ea6c

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY operator.py .

# Run as non-root user
RUN useradd -m -u 10001 -s /bin/sh otus \
  && chown -R otus:otus /app
USER otus

# kopf will use in-cluster config automatically
CMD ["kopf", "run", "--standalone", "/app/operator.py"]
