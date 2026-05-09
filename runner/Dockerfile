FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends gcc libc6-dev && rm -rf /var/lib/apt/lists/*

RUN useradd -m runner
WORKDIR /app
COPY runner.py /app/runner.py

USER runner
ENV RUNNER_HOST=0.0.0.0
ENV RUNNER_PORT=18080
EXPOSE 18080

CMD ["python","/app/runner.py"]

