"""Authorization Server OAuth 2.1 mínimo — fecha o open item #32d96c3d.

Os conectores hospedados (claude.ai / ChatGPT / Gemini) exigem um Authorization Server
COMPLETO: Dynamic Client Registration (RFC 7591) + authorization-code com PKCE (S256) +
metadata de discovery (RFC 8414). O Supabase Auth (GoTrue) é um IdP, não um AS OAuth
genérico com DCR — então o AS mora aqui, e DELEGA a autenticação do usuário ao Supabase.

Fluxo (cada passo é uma volta do navegador do usuário):
  1. /register  — o conector se registra dinamicamente (DCR). [rota do SDK MCP]
  2. /authorize — guardamos os params (PKCE challenge, redirect, state, scopes) sob um
     `ticket` opaco e mandamos o navegador ao NOSSO /oauth/login.            [rota do SDK]
  3. /oauth/login — autenticação do usuário, delegada ao Supabase. DOIS modos:
     (a) HOSPEDADO (produção, `login_provider` setado): redirect ao login social/SSO do
         GoTrue (`/auth/v1/authorize?provider=…`) com PKCE server-side NOSSO. A senha
         NUNCA toca nosso servidor. O GoTrue volta a /oauth/callback com `?code=…`.
     (b) FORMULÁRIO (dev/CLI, sem provider): form mínimo cujo POST entrega email+senha ao
         Supabase (`grant_type=password`/`signup`). Repassamos sobre TLS; nunca guardamos.
     Sucesso (em qualquer modo) → cunhamos NOSSO authorization code (ligado à sessão
     Supabase) e redirecionamos ao redirect_uri do conector com code+state.    [rotas nossas]
  3b. /oauth/callback — (modo hospedado) recebe o `code` do GoTrue, troca por sessão via
     `grant_type=pkce` (auth_code + code_verifier que guardamos sob o ticket).  [rota nossa]
  4. /token     — o SDK valida o PKCE verifier (S256) e o redirect; nós trocamos o code
     pelo access_token = o JWT do Supabase, que o Resource Server já valida por requisição
     (escopando a RLS por usuário). Refresh e revoke também batem no Supabase.  [rota do SDK]

Produção (endurecido #0084-AS): set `login_provider` (LIFELINE_OAUTH_PROVIDER=github) → modo
hospedado, sem ROPC. O formulário de senha fica só p/ dev/CLI (sem provider).

Persistência dos clients DCR: pluggable via `client_store`. Default EM MEMÓRIA (instância
única); `SupabaseClientStore` (ativado por SUPABASE_SERVICE_ROLE) persiste em
`lifeline_oauth_clients` → sobrevive a restart/sleep do Render e a múltiplas réplicas. Codes
seguem one-time/efêmeros (TTL ~300s), nunca persistidos.
"""
import base64
import hashlib
import logging
import secrets
import time
from typing import Any, Dict, Optional, Tuple
from urllib.parse import quote

import httpx
from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    OAuthAuthorizationServerProvider,
    RefreshToken,
    TokenError,
    construct_redirect_uri,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse

_log = logging.getLogger("lifeline.oauth")

_LOGIN_HTML = """<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Lifeline — entrar</title><style>
 body{{font:15px system-ui,sans-serif;background:#0b0c0f;color:#e7e9ee;display:grid;
 place-items:center;height:100vh;margin:0}}
 form{{background:#15171c;padding:28px;border-radius:12px;width:320px;box-shadow:0 8px 30px #0008}}
 h1{{font-size:17px;margin:0 0 4px}} p{{color:#9aa0ab;margin:0 0 18px;font-size:13px}}
 input[type=email],input[type=password]{{width:100%;box-sizing:border-box;margin:6px 0;padding:10px;
 border-radius:8px;border:1px solid #2a2e37;background:#0d0f13;color:#e7e9ee}}
 button{{width:100%;margin-top:12px;padding:11px;border:0;border-radius:8px;background:#4f8cff;
 color:#fff;font-weight:600;cursor:pointer}} .err{{color:#ff6b6b;font-size:13px;min-height:18px}}
 label.cb{{display:flex;align-items:center;gap:8px;color:#9aa0ab;font-size:13px;margin-top:10px}}
 label.cb input{{width:auto;margin:0}}
</style></head><body><form method="post" action="/oauth/login">
 <h1>Lifeline</h1><p>Entre (ou crie sua conta) no Supabase para autorizar o conector.</p>
 <div class="err">{error}</div>
 <input type="hidden" name="ticket" value="{ticket}">
 <input name="email" type="email" placeholder="email" autocomplete="username" required autofocus>
 <input name="password" type="password" placeholder="senha" autocomplete="current-password" required>
 <label class="cb"><input type="checkbox" name="signup" value="1"> Criar conta (primeiro acesso)</label>
 <button type="submit">Continuar</button>
</form></body></html>"""


# ---- store dos clients DCR (pluggable: memória p/ instância única; Supabase p/ persistir) ----
class ClientStore:
    """Porta do registro de clients DCR. `get` devolve o client ou None; `put` persiste."""
    async def get(self, client_id: str) -> Optional[OAuthClientInformationFull]:
        raise NotImplementedError

    async def put(self, client: OAuthClientInformationFull) -> None:
        raise NotImplementedError


class InMemoryClientStore(ClientStore):
    """Default: dict em processo. Correto p/ instância única; some no restart (por isso o
    deploy escalado/efêmero usa o SupabaseClientStore)."""
    def __init__(self):
        self._d: Dict[str, OAuthClientInformationFull] = {}

    async def get(self, client_id):
        return self._d.get(client_id)

    async def put(self, client):
        self._d[client.client_id] = client


class SupabaseClientStore(ClientStore):
    """Persiste os clients DCR em `lifeline_oauth_clients` via PostgREST. O registro acontece
    ANTES do login (não há uid p/ RLS), então usa a chave de SERVIÇO — é infra do AS, não dado
    de tenant (ver schema.sql:84-98). `transport` injetável p/ teste."""
    def __init__(self, *, url: str, service_key: str, transport: Any = None):
        from lifeline.cloud import clean_url
        self.url = clean_url(url)
        self.key = (service_key or "").strip()
        self._transport = transport

    def _headers(self) -> Dict[str, str]:
        return {"apikey": self.key, "Authorization": f"Bearer {self.key}",
                "Content-Type": "application/json"}

    async def get(self, client_id):
        try:
            async with httpx.AsyncClient(timeout=15, transport=self._transport) as c:
                r = await c.get(f"{self.url}/rest/v1/lifeline_oauth_clients",
                                params={"client_id": f"eq.{client_id}", "select": "client_info"},
                                headers=self._headers())
        except Exception:
            _log.exception("client store get: falha de rede/URL")
            return None
        if r.status_code != 200:
            _log.info("client store get -> %s", r.status_code)
            return None
        rows = r.json() or []
        if not rows:
            return None
        try:
            return OAuthClientInformationFull.model_validate(rows[0]["client_info"])
        except Exception:
            _log.exception("client store: client_info inválido na tabela")
            return None

    async def put(self, client):
        # upsert idempotente: merge-duplicates no PK client_id (re-registro do mesmo conector não duplica)
        try:
            async with httpx.AsyncClient(timeout=15, transport=self._transport) as c:
                r = await c.post(f"{self.url}/rest/v1/lifeline_oauth_clients",
                                 params={"on_conflict": "client_id"},
                                 headers={**self._headers(),
                                          "Prefer": "resolution=merge-duplicates,return=minimal"},
                                 json={"client_id": client.client_id,
                                       "client_info": client.model_dump(mode="json")})
            if r.status_code >= 300:
                _log.error("client store put -> %s: %s", r.status_code, r.text[:200])
        except Exception:
            _log.exception("client store put: falha de rede/URL")


class SupabaseAuthServer(
    OAuthAuthorizationServerProvider[AuthorizationCode, RefreshToken, AccessToken]
):
    """Provider do AS. DCR + authorization-code/PKCE; autentica o usuário no Supabase.
    `transport` é injetável (httpx.MockTransport) para teste, igual a lifeline/cloud.py."""

    def __init__(self, *, supabase_url: str, supabase_key: str, public_url: str,
                 transport: Any = None, code_ttl: int = 300,
                 login_provider: Optional[str] = None,
                 client_store: Optional[ClientStore] = None):
        from lifeline.cloud import clean_url
        self.url = clean_url(supabase_url)           # garante https:// (erro comum no deploy)
        self.key = (supabase_key or "").strip()
        self.public_url = clean_url(public_url)
        self._transport = transport
        self.code_ttl = code_ttl
        # provider social/SSO p/ o login HOSPEDADO (ex.: "github"). None → cai no form de senha (dev).
        self.login_provider = (login_provider or "").strip() or None
        # registro de clients DCR: in-memory (default) ou persistente (Supabase) — pluggable.
        self._store: ClientStore = client_store or InMemoryClientStore()
        self._client_cache: Dict[str, OAuthClientInformationFull] = {}   # cache em frente ao store
        self._tickets: Dict[str, Tuple[str, AuthorizationParams]] = {}
        self._pkce: Dict[str, str] = {}              # ticket → code_verifier do Supabase (modo hospedado)
        self._codes: Dict[str, Tuple[AuthorizationCode, Dict]] = {}  # code → (AuthCode, sessão Supabase)

    # ---- httpx p/ o Supabase (mock-friendly) --------------------------------------------
    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=15, transport=self._transport)

    async def _supabase_token(self, grant: str, payload: Dict) -> Optional[Dict]:
        """Bate em /auth/v1/token?grant_type=… (password|refresh_token). 200 → sessão; senão None.
        Qualquer erro de rede/URL é LOGADO e vira None (nunca 500 cru no fluxo de login)."""
        try:
            async with self._client() as c:
                r = await c.post(f"{self.url}/auth/v1/token", params={"grant_type": grant},
                                 json=payload, headers={"apikey": self.key,
                                                        "Content-Type": "application/json"})
        except Exception:
            _log.exception("Supabase token grant=%s: falha de rede/URL", grant)
            return None
        if r.status_code != 200:
            _log.info("Supabase token grant=%s -> %s", grant, r.status_code)
            return None
        try:
            return r.json()
        except Exception:
            _log.exception("Supabase token: resposta não-JSON")
            return None

    async def _supabase_signup(self, email: str, password: str) -> Tuple[Optional[Dict], Optional[str]]:
        """Cria a conta no Supabase (/auth/v1/signup). Sem isto, o 1º usuário que conecta pelo
        navegador (claude.ai) não tem conta e fica travado. Retorna (sessão, None) quando o
        projeto auto-confirma (login imediato); (None, mensagem) quando precisa confirmar por
        email (não dá pra completar inline) ou quando a conta já existe / falha."""
        try:
            async with self._client() as c:
                r = await c.post(f"{self.url}/auth/v1/signup",
                                 json={"email": email, "password": password},
                                 headers={"apikey": self.key, "Content-Type": "application/json"})
        except Exception:
            _log.exception("Supabase signup: falha de rede/URL")
            return None, "serviço de autenticação indisponível — tente de novo em instantes."
        if r.status_code not in (200, 201):
            _log.info("Supabase signup -> %s", r.status_code)
            return None, "não foi possível criar a conta (talvez já exista — tente entrar)."
        try:
            data = r.json() or {}
        except Exception:
            return None, "resposta inválida do serviço de autenticação."
        sess = data if data.get("access_token") else (data.get("session") or {})
        if sess.get("access_token"):
            return sess, None
        # 200 sem token → confirmação por email ligada no projeto Supabase
        return None, "conta criada — confirme pelo email e volte para entrar."

    # ---- DCR (RFC 7591) — via ClientStore (cache em frente) -----------------------------
    async def get_client(self, client_id: str) -> Optional[OAuthClientInformationFull]:
        c = self._client_cache.get(client_id)
        if c is not None:
            return c
        c = await self._store.get(client_id)         # busca persistente (sobrevive a restart)
        if c is not None:
            self._client_cache[client_id] = c
        return c

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        self._client_cache[client_info.client_id] = client_info   # disponível já nesta request
        await self._store.put(client_info)                        # persiste (best-effort no store)

    # ---- authorize → manda o usuário pro nosso login (que delega ao Supabase) -----------
    async def authorize(self, client: OAuthClientInformationFull,
                        params: AuthorizationParams) -> str:
        ticket = secrets.token_urlsafe(32)
        self._tickets[ticket] = (client.client_id, params)
        return f"{self.public_url}/oauth/login?ticket={ticket}"

    # ---- rotas do nosso login (registradas via _register_login_routes) ------------------
    def _new_pkce(self) -> Tuple[str, str]:
        """Par PKCE (verifier, challenge S256) p/ o handshake NOSSO↔GoTrue no modo hospedado.
        Separado do PKCE conector↔nós (esse o SDK gerencia)."""
        verifier = secrets.token_urlsafe(64)[:96]    # 43–128 chars (RFC 7636)
        challenge = base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
        return verifier, challenge

    async def login_get(self, request: Request):
        ticket = request.query_params.get("ticket", "")
        if not self.login_provider:                  # modo dev/CLI: formulário de senha
            return HTMLResponse(_LOGIN_HTML.format(ticket=ticket, error=""))
        # modo HOSPEDADO: manda o navegador ao login social do Supabase (a senha não nos toca).
        if ticket not in self._tickets:
            return HTMLResponse(_LOGIN_HTML.format(ticket="", error="sessão expirada — recomece"),
                                status_code=400)
        verifier, challenge = self._new_pkce()
        self._pkce[ticket] = verifier                # guardamos o verifier p/ o /oauth/callback
        cb = f"{self.public_url}/oauth/callback?ticket={ticket}"
        authz = (f"{self.url}/auth/v1/authorize?provider={quote(self.login_provider, safe='')}"
                 f"&redirect_to={quote(cb, safe='')}"
                 f"&code_challenge={challenge}&code_challenge_method=s256")
        return RedirectResponse(url=authz, status_code=302)

    async def login_post(self, request: Request):
        try:
            return await self._login_post(request)
        except Exception:   # rede-de-segurança: nunca 500 cru no login (loga o porquê)
            _log.exception("login_post: erro inesperado")
            return HTMLResponse(_LOGIN_HTML.format(
                ticket="", error="erro interno ao autorizar — recomece a conexão"), status_code=500)

    async def _login_post(self, request: Request):
        form = await request.form()
        ticket = str(form.get("ticket", ""))
        entry = self._tickets.get(ticket)
        if not entry:
            return HTMLResponse(_LOGIN_HTML.format(ticket="", error="sessão expirada — recomece"),
                                status_code=400)
        client_id, params = entry
        email, password = str(form.get("email", "")), str(form.get("password", ""))
        if form.get("signup"):                         # primeiro acesso: cria a conta no Supabase
            session, msg = await self._supabase_signup(email, password)
            if not session:
                return HTMLResponse(_LOGIN_HTML.format(ticket=ticket, error=msg or "falha no cadastro"),
                                    status_code=400)
        else:
            session = await self._supabase_token("password", {"email": email, "password": password})
            if not session or "access_token" not in session:
                return HTMLResponse(_LOGIN_HTML.format(ticket=ticket, error="credenciais inválidas"),
                                    status_code=401)
        return self._mint_and_redirect(ticket, client_id, params, session)

    async def oauth_callback(self, request: Request):
        """(modo hospedado) O GoTrue volta aqui com `?ticket=…&code=…` após o login social.
        Trocamos o code pela sessão (grant_type=pkce, com o verifier guardado) e cunhamos o
        NOSSO authorization code. Nenhuma senha passou por aqui."""
        ticket = request.query_params.get("ticket", "")
        code = request.query_params.get("code", "")
        err = request.query_params.get("error_description") or request.query_params.get("error")
        entry = self._tickets.get(ticket)
        verifier = self._pkce.get(ticket)
        if not entry or not verifier:
            return HTMLResponse(_LOGIN_HTML.format(ticket="", error="sessão expirada — recomece"),
                                status_code=400)
        if err or not code:                            # login negado/cancelado no provedor
            self._tickets.pop(ticket, None)
            self._pkce.pop(ticket, None)
            return HTMLResponse(_LOGIN_HTML.format(
                ticket="", error="login não concluído — recomece a conexão"), status_code=400)
        client_id, params = entry
        session = await self._supabase_token("pkce", {"auth_code": code, "code_verifier": verifier})
        self._pkce.pop(ticket, None)
        if not session or "access_token" not in session:
            self._tickets.pop(ticket, None)
            return HTMLResponse(_LOGIN_HTML.format(
                ticket="", error="não foi possível concluir o login — recomece"), status_code=401)
        return self._mint_and_redirect(ticket, client_id, params, session)

    def _mint_and_redirect(self, ticket: str, client_id: str,
                           params: AuthorizationParams, session: Dict):
        """Consome o ticket, cunha NOSSO authorization code (ligado à sessão Supabase) e
        redireciona ao redirect_uri do conector com code+state. Compartilhado pelos dois modos."""
        self._tickets.pop(ticket, None)
        code = secrets.token_urlsafe(32)
        self._codes[code] = (AuthorizationCode(
            code=code, scopes=params.scopes or [], expires_at=time.time() + self.code_ttl,
            client_id=client_id, code_challenge=params.code_challenge,
            redirect_uri=params.redirect_uri,
            redirect_uri_provided_explicitly=params.redirect_uri_provided_explicitly,
            resource=params.resource), session)
        target = construct_redirect_uri(str(params.redirect_uri), code=code, state=params.state)
        return RedirectResponse(url=target, status_code=302)

    # ---- token: load + exchange (o SDK já verifica PKCE/redirect antes do exchange) ------
    async def load_authorization_code(self, client: OAuthClientInformationFull,
                                      authorization_code: str) -> Optional[AuthorizationCode]:
        rec = self._codes.get(authorization_code)
        if not rec:
            return None
        ac, _session = rec
        if ac.client_id != client.client_id or ac.expires_at < time.time():
            return None
        return ac

    async def exchange_authorization_code(self, client: OAuthClientInformationFull,
                                          authorization_code: AuthorizationCode) -> OAuthToken:
        rec = self._codes.pop(authorization_code.code, None)  # one-time: consome o code
        if not rec:
            raise TokenError("invalid_grant", "authorization code inválido ou já usado")
        _ac, session = rec
        return OAuthToken(
            access_token=session["access_token"], token_type="Bearer",
            expires_in=session.get("expires_in", 3600),
            refresh_token=session.get("refresh_token"),
            scope=" ".join(authorization_code.scopes) or None)

    # ---- refresh: delega ao Supabase ----------------------------------------------------
    async def load_refresh_token(self, client: OAuthClientInformationFull,
                                 refresh_token: str) -> Optional[RefreshToken]:
        # opaco: o refresh é o do Supabase. Devolve um envelope; o exchange valida ao usar.
        return RefreshToken(token=refresh_token, client_id=client.client_id,
                            scopes=[], expires_at=None)

    async def exchange_refresh_token(self, client: OAuthClientInformationFull,
                                     refresh_token: RefreshToken, scopes: list) -> OAuthToken:
        session = await self._supabase_token("refresh_token", {"refresh_token": refresh_token.token})
        if not session or "access_token" not in session:
            raise TokenError("invalid_grant", "refresh token inválido/expirado no Supabase")
        return OAuthToken(
            access_token=session["access_token"], token_type="Bearer",
            expires_in=session.get("expires_in", 3600),
            refresh_token=session.get("refresh_token", refresh_token.token),
            scope=" ".join(scopes) or None)

    # ---- token introspection p/ o Resource Server (ProviderTokenVerifier chama isto) ----
    async def load_access_token(self, token: str) -> Optional[AccessToken]:
        if not token:
            return None
        try:
            async with self._client() as c:
                r = await c.get(f"{self.url}/auth/v1/user",
                                headers={"apikey": self.key, "Authorization": f"Bearer {token}"})
        except Exception:
            _log.exception("Supabase /user: falha de rede/URL")
            return None
        if r.status_code != 200:
            return None
        uid = (r.json() or {}).get("id", "unknown")
        return AccessToken(token=token, client_id=uid, scopes=["lifeline"], expires_at=None)

    async def revoke_token(self, token: Any) -> None:
        tok = getattr(token, "token", None)
        if not tok:
            return
        try:
            async with self._client() as c:
                await c.post(f"{self.url}/auth/v1/logout",
                             headers={"apikey": self.key, "Authorization": f"Bearer {tok}"})
        except Exception:  # logout best-effort: o token expira sozinho de qualquer forma
            _log.debug("revoke (Supabase logout) falhou — token expira por TTL", exc_info=True)

    # ---- registra as rotas do nosso login numa instância FastMCP ------------------------
    def register_login_routes(self, server) -> None:
        server.custom_route("/oauth/login", methods=["GET"])(self.login_get)
        server.custom_route("/oauth/login", methods=["POST"])(self.login_post)
        server.custom_route("/oauth/callback", methods=["GET"])(self.oauth_callback)  # modo hospedado
