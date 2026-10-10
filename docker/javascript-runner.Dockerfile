FROM node:22-bookworm-slim

RUN useradd --create-home --uid 65532 --shell /usr/sbin/nologin runner

RUN npm install --global typescript@5.7.3

ENV NODE_PATH=/usr/local/lib/node_modules
COPY docker/tools/javascript /opt/antislop/javascript
COPY docker/tools/javascript_*.cjs /opt/antislop/

WORKDIR /workspace
USER 65532:65532
