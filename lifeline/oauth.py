"""Authorization Server OAuth 2.1 mínimo — fecha o open item #32d96c3d.

Os conectores hospedados (claude.ai / ChatGPT / Gemini) exigem um Authorization Server
COMPLETO: Dynamic Client Registration (RFC 7591) + authorization-code com PKCE (S256) +
metadata de discovery (RFC 8414). O Supabase Auth (GoTrue) é um IdP, não um AS OAuth
genérico com DCR — então o AS mora aqui, e DELEGA a autenticação do usuário ao Supabase.

Fluxo (cada passo é uma volta do navegador do usuário):
  1. /register  — o conector se registra dinamicamente (DCR). [rota do SDK MCP]
  2. /authorize — guardamos os params (PKCE challenge, redirect, state, scopes) sob um
     `ticket` opaco e mandamos o navegador ao NOSSO /oauth/login.            [rota do SDK]
  3. /oauth/login — formulário mínimo (entrar OU criar conta no primeiro acesso); o POST
     entrega email+senha ao Supabase (`grant_type=password`, ou `/auth/v1/signup`). Nós NUNCA
     guardamos/validamos a senha — o Supabase o faz; só repassamos sobre TLS. Sucesso →
     cunhamos NOSSO authorization code (ligado à sessão Supabase) e redirecionamos ao
     redirect_uri do conector com code+state. (Sign-up inline exige o projeto Supabase com
     auto-confirm; com confirmação por email, o usuário confirma e volta para entrar.) [rota nossa]
  4. /token     — o SDK valida o PKCE verifier (S256) e o redirect; nós trocamos o code
     pelo access_token = o JWT do Supabase, que o Resource Server já valida por requisição
     (escopando a RLS por usuário). Refresh e revoke também batem no Supabase.  [rota do SDK]

Limites DECLARADOS (honestidade #0046/#0047):
  - Grant de SENHA (ROPC): nosso servidor vê a senha em trânsito. É o mínimo testável e
    sem config de dashboard. Hardening de produção: trocar o /oauth/login por redirect ao
    login HOSPEDADO do Supabase (SSO/social, fluxo PKCE do GoTrue) — o AS aqui não muda,
    só o passo 3. Ver docs/MCP_REMOTE.md.
  - Armazenamento de clients/codes é EM MEMÓRIA: correto para instância única (o deploy
    atual). Multi-instância precisa de store compartilhado (tabela `lifeline_oauth_clients`
    já no schema.sql). Codes são one-time e expiram (default 300s).
"""
import logging
import secrets
import time
from typing import Any, Dict, Optional, Tuple

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


class SupabaseAuthServer(
    OAuthAuthorizationServerProvider[AuthorizationCode, RefreshToken, AccessToken]
):
    """Provider do AS. DCR + authorization-code/PKCE; autentica o usuário no Supabase.
    `transport` é injetável (httpx.MockTransport) para teste, igual a lifeline/cloud.py."""

    def __init__(self, *, supabase_url: str, supabase_key: str, public_url: str,
                 transport: Any = None, code_ttl: int = 300):
        self.url = supabase_url.rstrip("/")
        self.key = supabase_key
        self.public_url = public_url.rstrip("/")
        self._transport = transport
        self.code_ttl = code_ttl
        self._clients: Dict[str, OAuthClientInformationFull] = {}
        self._tickets: Dict[str, Tuple[str, AuthorizationParams]] = {}
        self._codes: Dict[str, Tuple[AuthorizationCode, Dict]] = {}  # code → (AuthCode, sessão Supabase)

    # ---- httpx p/ o Supabase (mock-friendly) --------------------------------------------
    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=15, transport=self._transport)

    async def _supabase_token(self, grant: str, payload: Dict) -> Optional[Dict]:
        """Bate em /auth/v1/token?grant_type=… (password|refresh_token). 200 → sessão; senão None."""
        async with self._client() as c:
            r = await c.post(f"{self.url}/auth/v1/token", params={"grant_type": grant},
                             json=payload, headers={"apikey": self.key,
                                                    "Content-Type": "application/json"})
        if r.status_code != 200:
            _log.info("Supabase token grant=%s -> %s", grant, r.status_code)
            return None
        return r.json()

    async def _supabase_signup(self, email: str, password: str) -> Tuple[Optional[Dict], Optional[str]]:
        """Cria a conta no Supabase (/auth/v1/signup). Sem isto, o 1º usuário que conecta pelo
        navegador (claude.ai) não tem conta e fica travado. Retorna (sessão, None) quando o
        projeto auto-confirma (login imediato); (None, mensagem) quando precisa confirmar por
        email (não dá pra completar inline) ou quando a conta já existe / falha."""
        async with self._client() as c:
            r = await c.post(f"{self.url}/auth/v1/signup",
                             json={"email": email, "password": password},
                             headers={"apikey": self.key, "Content-Type": "application/json"})
        if r.status_code not in (200, 201):
            _log.info("Supabase signup -> %s", r.status_code)
            return None, "não foi possível criar a conta (talvez já exista — tente entrar)."
        data = r.json() or {}
        sess = data if data.get("access_token") else (data.get("session") or {})
        if sess.get("access_token"):
            return sess, None
        # 200 sem token → confirmação por email ligada no projeto Supabase
        return None, "conta criada — confirme pelo email e volte para entrar."

    # ---- DCR (RFC 7591) -----------------------------------------------------------------
    async def get_client(self, client_id: str) -> Optional[OAuthClientInformationFull]:
        return self._clients.get(client_id)

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        self._clients[client_info.client_id] = client_info

    # ---- authorize → manda o usuário pro nosso login (que delega ao Supabase) -----------
    async def authorize(self, client: OAuthClientInformationFull,
                        params: AuthorizationParams) -> str:
        ticket = secrets.token_urlsafe(32)
        self._tickets[ticket] = (client.client_id, params)
        return f"{self.public_url}/oauth/login?ticket={ticket}"

    # ---- rotas do nosso login (registradas via _register_login_routes) ------------------
    async def login_get(self, request: Request) -> HTMLResponse:
        ticket = request.query_params.get("ticket", "")
        return HTMLResponse(_LOGIN_HTML.format(ticket=ticket, error=""))

    async def login_post(self, request: Request):
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
        async with self._client() as c:
            r = await c.get(f"{self.url}/auth/v1/user",
                            headers={"apikey": self.key, "Authorization": f"Bearer {token}"})
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
