# Lifeline — servidor MCP remoto AUTHLESS (validação do one-click no claude.ai).
# A line vive como SQLite no host, reconstruída no boot a partir da LIFELINE.md versionada
# (o .db é cache reconstruível — decisão #0022). Sem LIFELINE_OAUTH → authless (single-tenant).
FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir -e ".[cloud,remote]"  # remote = python-multipart (AS OAuth: /oauth/login e /token)

ENV LIFELINE_MCP_TRANSPORT=streamable-http \
    LIFELINE_MCP_HOST=0.0.0.0 \
    LIFELINE_DB=.lifeline/ledger.db
EXPOSE 8000

# reconstrói o .db da view e serve authless. ${PORT} respeita Render/Railway (senão 8000).
CMD lifeline migrate --from LIFELINE.md && LIFELINE_MCP_PORT=${PORT:-8000} lifeline-mcp-remote
