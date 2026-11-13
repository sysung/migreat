FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml LICENSE ./
COPY migreat/ migreat/
RUN python -m pip install --no-cache-dir .

USER 65532:65532
WORKDIR /work
ENTRYPOINT ["migreat"]
CMD ["--help"]
