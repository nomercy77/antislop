FROM python:3.12-slim

RUN useradd --create-home --uid 65532 --shell /usr/sbin/nologin runner \
    && python -m pip install --no-cache-dir mypy==1.14.1 pytest==8.3.5

COPY docker/tools/python /opt/antislop/python
COPY docker/tools/python_*.py /opt/antislop/

WORKDIR /workspace
USER 65532:65532
