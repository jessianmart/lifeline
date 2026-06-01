"""Superfície MCP — a interface da IA é o produto (Lei #7).

  - LER ao conectar:  resource `lifeline://project/context` + tool `lifeline_recall`.
  - PROPOR ao trabalhar:  `lifeline_append` / `lifeline_recontextualize` — escrita HITL:
    vira PROPOSTA pendente; um humano aprova antes de entrar na line.

Três modos, mesma superfície (registrada por `_register`):
  - LOCAL (stdio, SQLite):   LIFELINE_DB=…  lifeline-mcp
  - REMOTO (HTTP/SSE, nuvem): LIFELINE_STORE=supabase  SUPABASE_URL/KEY/TOKEN=…  lifeline-mcp-remote
  - REMOTO + OAuth (multi-tenant): idem, e o servidor vira um OAuth Resource Server —
    valida o Bearer JWT de CADA requisição (Supabase) e escopa o store por usuário
    (RLS `owner=auth.uid()`). Liga com LIFELINE_OAUTH=1.

Honestidade (#0046/#0047): o Resource Server (validação de token + metadata de
protected-resource + multi-tenant) está pronto e testado aqui. O Authorization Server
completo (DCR + authorization-code) que os conectores claude.ai/ChatGPT/Gemini exigem
depende de um AS compatível — o Supabase Auth não é um AS OAuth genérico com DCR. Ver
docs/MCP_REMOTE.md.
"""
import logging
import os
from typing import Optional

import httpx
from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from lifeline.cli import _STORE, _open, _staging, _validate

_DB = os.environ.get("LIFELINE_DB", os.path.join(".lifeline", "ledger.db"))
_AUTHOR = os.environ.get("LIFELINE_AUTHOR", "mcp")

# Manual de uso entregue a TODA IA que conecta (FastMCP envia no initialize). AI-first: a IA
# se onboarda sozinha, segue o loop, e sabe explicar/organizar pro humano.
_INSTRUCTIONS = (
    "Lifeline é o ledger de RACIOCÍNIO deste projeto (o *porquê*), append-only e "
    "content-addressed. AO CONECTAR: leia PRIMEIRO o resource `lifeline://project/context` — "
    "é a verdade montada (o quê / por quê / decidido / próximo); aja a partir dela. Use "
    "`lifeline_recall(query)` para 'já decidimos algo sobre X?'. AO TRABALHAR: a cada "
    "decisão/feature/fix/incidente com significado, PROPONHA via `lifeline_append(kind, summary, "
    "body)` — o body é o *porquê* (obrigatório). Reverteu/atualizou algo: "
    "`lifeline_recontextualize(parent_id, ...)`. Você NÃO grava na verdade: a escrita é HITL — "
    "entra como PROPOSTA e o humano aprova/rejeita. NUNCA invente: toda afirmação ancora numa "
    "entrada. SEU PAPEL com o humano: explique o que o Lifeline é, mantenha o contexto "
    "ORGANIZADO (aponte as decisões em vigor, sinalize threads fechadas, proponha entradas pelo "
    "trabalho feito) — mas quem cura é ele. Não aceite sujeira."
)


def _configure() -> None:
    """Escolhe backend/line pelo ambiente (mesmo `_STORE` que a CLI usa em _open/_staging)."""
    _STORE["kind"] = os.environ.get("LIFELINE_STORE", "sqlite")
    _STORE["line"] = os.environ.get("LIFELINE_LINE", "ledger")


# ---- multi-tenant: token do usuário (do request OAuth) escopa o store por RLS -------------

def _request_token() -> Optional[str]:
    """JWT do usuário autenticado nesta requisição (None fora de contexto/sem auth)."""
    try:
        from mcp.server.auth.middleware.auth_context import get_access_token
        at = get_access_token()
        return at.token if at else None
    except Exception:
        logging.getLogger("lifeline.mcp").debug("sem contexto de auth na requisição", exc_info=True)
        return None


async def _open_request():
    """Store da requisição: na nuvem com token de usuário → escopa por RLS; senão, factory padrão."""
    tok = _request_token()
    if _STORE["kind"] == "supabase" and tok:
        from lifeline.cloud import SupabaseEventStore
        s = SupabaseEventStore(line=_STORE["line"], token=tok)
        await s.initialize()
        return s
    return await _open(_DB)


def _staging_request():
    tok = _request_token()
    if _STORE["kind"] == "supabase" and tok:
        from lifeline.cloud import SupabaseStagingStore
        return SupabaseStagingStore(line=_STORE["line"], token=tok)
    return _staging(_DB)


# ---- handlers (registrados em qualquer instância FastMCP por _register) -------------------

async def project_context() -> str:
    """O contexto do projeto, montado e dentro do budget — leia isto ao conectar."""
    from lifeline.context import ContextAssembler
    from lifeline.state import StateEngine
    store = await _open_request()
    return await ContextAssembler(StateEngine(store)).assemble()


async def lifeline_append(kind: str, summary: str, body: str = "",
                          agent: str = "mcp-agent", provider: str = "none",
                          model: str = "unknown") -> str:
    """PROPÕE uma entrada (decisão/feature/fix/incident/milestone/note/open). Entra como
    PENDENTE — um humano aprova via `lifeline review`/`approve` antes de virar parte da line
    (HITL). O *porquê* importa mais que o *quê* — diga-o no body (obrigatório)."""
    try:
        _validate(kind, body)
    except ValueError as ex:
        return f"recusado: {ex}"
    staging = _staging_request()
    await staging.initialize()
    pid = await staging.propose(kind=kind, summary=summary, body=body, author=_AUTHOR,
                                agent=agent, provider=provider, model=model, parents=None)
    return f"proposta #{pid} enfileirada ({kind}) — PENDENTE de aprovação humana (lifeline review)"


async def lifeline_recontextualize(parent_id: str, summary: str, body: str = "",
                                   agent: str = "mcp-agent", provider: str = "none",
                                   model: str = "unknown") -> str:
    """PROPÕE uma correção que supersede a entrada `parent_id` (decisão revertida, thread
    fechada, fato atualizado). Append-only, nunca edição (Lei #2). Fica PENDENTE até um
    humano aprovar (HITL). Diga o *porquê* da mudança no body (obrigatório)."""
    try:
        _validate("correction", body)
    except ValueError as ex:
        return f"recusado: {ex}"
    staging = _staging_request()
    await staging.initialize()
    pid = await staging.propose(kind="correction", summary=summary, body=body, author=_AUTHOR,
                                agent=agent, provider=provider, model=model, parents=[parent_id])
    return f"correção proposta #{pid} (supersede {parent_id[:12]}) — PENDENTE de aprovação"


async def lifeline_recall(query: str, k: int = 5) -> str:
    """Recupera as entradas mais RELEVANTES à tarefa atual (Camada 3 — ancoradas).
    Use para "já decidimos algo sobre X?" sem ler o ledger inteiro. Relevância, não recência."""
    from lifeline.recall import SemanticRecall, make_embedder
    store = await _open_request()
    hits = await SemanticRecall(store, make_embedder()).search(query, k=k)
    if not hits:
        return "Nada relevante encontrado no ledger."
    return "\n".join(
        f"[{h['kind']}] {h['summary']} (id={h['id'][:12]}, score={h['score']})" for h in hits
    )


async def _healthz(_request):
    """Liveness simples (GET 200) — health check de plataformas (Render/Railway) e checagem
    no navegador de que o servidor está no ar. Não expõe dado."""
    from starlette.responses import PlainTextResponse
    return PlainTextResponse("ok")


def _register(server: FastMCP) -> FastMCP:
    """Registra a MESMA superfície em qualquer instância (com ou sem auth)."""
    server.resource("lifeline://project/context")(project_context)
    server.tool()(lifeline_append)
    server.tool()(lifeline_recontextualize)
    server.tool()(lifeline_recall)
    server.custom_route("/healthz", methods=["GET"])(_healthz)
    return server


# instância default (local/stdio e testes) — sem auth
mcp = _register(FastMCP("Lifeline", instructions=_INSTRUCTIONS))


# ---- OAuth Resource Server (multi-tenant) -------------------------------------------------

class SupabaseTokenVerifier(TokenVerifier):
    """Valida o Bearer JWT contra o Supabase (`/auth/v1/user`). Token válido → AccessToken
    carregando o próprio JWT (usado p/ escopar a RLS por usuário) e o user id. `transport`
    injetável p/ teste."""

    def __init__(self, url: Optional[str] = None, key: Optional[str] = None, transport=None):
        self.url = (url or os.environ.get("SUPABASE_URL", "")).rstrip("/")
        self.key = key or os.environ.get("SUPABASE_KEY")
        self._transport = transport

    async def verify_token(self, token: str) -> Optional[AccessToken]:
        if not (self.url and self.key and token):
            return None
        async with httpx.AsyncClient(timeout=15, transport=self._transport) as c:
            r = await c.get(f"{self.url}/auth/v1/user",
                            headers={"apikey": self.key, "Authorization": f"Bearer {token}"})
        if r.status_code != 200:
            return None  # inválido/expirado → 401
        uid = (r.json() or {}).get("id", "unknown")
        return AccessToken(token=token, client_id=uid, scopes=["lifeline"], expires_at=None)


def _transport_security() -> TransportSecuritySettings:
    """Atrás de túnel/proxy/deploy o Host header é o domínio público — o default localhost-only
    do FastMCP bloqueia com 421 'Invalid Host header'. `LIFELINE_MCP_ALLOWED_HOSTS=host1,host2`
    libera esses (proteção anti-DNS-rebinding ON); sem ele, desliga a proteção (o servidor remoto
    já é público de qualquer forma)."""
    hosts = os.environ.get("LIFELINE_MCP_ALLOWED_HOSTS", "").strip()
    if hosts:
        allow = []
        for h in (x.strip() for x in hosts.split(",") if x.strip()):
            allow += [h, f"{h}:*"]
        return TransportSecuritySettings(allowed_hosts=allow)
    return TransportSecuritySettings(enable_dns_rebinding_protection=False)


def _build_remote() -> FastMCP:
    """Servidor remoto. Com LIFELINE_OAUTH=1 (+ supabase + creds) vira Resource Server OAuth:
    exige Bearer válido e escopa por usuário. Senão, serve sem auth (single-tenant via env).
    Sempre com transport_security que aceita o host público (túnel/proxy/deploy)."""
    ts = _transport_security()
    oauth = os.environ.get("LIFELINE_OAUTH") == "1"
    if oauth and _STORE["kind"] == "supabase" and os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_KEY"):
        from mcp.server.auth.settings import AuthSettings
        issuer = os.environ.get("LIFELINE_OAUTH_ISSUER",
                                f"{os.environ['SUPABASE_URL'].rstrip('/')}/auth/v1")
        port = int(os.environ.get("LIFELINE_MCP_PORT", "8000"))
        resource = os.environ.get("LIFELINE_MCP_PUBLIC_URL", f"http://localhost:{port}")
        return _register(FastMCP(
            "Lifeline", instructions=_INSTRUCTIONS,
            token_verifier=SupabaseTokenVerifier(),
            auth=AuthSettings(issuer_url=issuer, resource_server_url=resource, required_scopes=[]),
            transport_security=ts,
        ))
    return _register(FastMCP("Lifeline", instructions=_INSTRUCTIONS, transport_security=ts))


def main():
    """Entry point (`lifeline-mcp`) — serve via stdio (local)."""
    _configure()
    mcp.run()


def main_remote():
    """Entry point (`lifeline-mcp-remote`) — serve por HTTP/SSE (superfície remota).

    Bind via LIFELINE_MCP_HOST/PORT (default 0.0.0.0:8000); transporte
    LIFELINE_MCP_TRANSPORT ('sse' default ou 'streamable-http'). LIFELINE_OAUTH=1 liga o
    Resource Server (Bearer obrigatório, multi-tenant). Escrita continua HITL.
    """
    _configure()
    server = _build_remote()
    server.settings.host = os.environ.get("LIFELINE_MCP_HOST", "0.0.0.0")
    server.settings.port = int(os.environ.get("LIFELINE_MCP_PORT", "8000"))
    server.run(transport=os.environ.get("LIFELINE_MCP_TRANSPORT", "sse"))


if __name__ == "__main__":
    main()
