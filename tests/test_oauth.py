"""Prova o Authorization Server (open item #32d96c3d): DCR, authorize→login→code, troca de
code por token (PKCE verificado pelo SDK), refresh, introspecção e revoke. O Supabase é
mockado via httpx.MockTransport (mesma disciplina de tests/test_supabase.py — wire, não live)."""
import base64
import hashlib
import os
import sys
import unittest
from unittest import mock

import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.server.auth.provider import AuthorizationParams, TokenError  # noqa: E402
from mcp.shared.auth import OAuthClientInformationFull                # noqa: E402

from lifeline.oauth import (                                          # noqa: E402
    SupabaseAuthServer, SupabaseClientStore, InMemoryClientStore)
from lifeline import mcp_server as srv                                 # noqa: E402
from lifeline import cli                                               # noqa: E402


def _pkce():
    verifier = "abc123abc123abc123abc123abc123abc123abc123abc"
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).decode().rstrip("=")
    return verifier, challenge


def _client(cid="c-1", redirect="https://conector.example/callback"):
    return OAuthClientInformationFull(
        client_id=cid, client_secret="s", redirect_uris=[redirect],
        grant_types=["authorization_code", "refresh_token"], response_types=["code"],
        token_endpoint_auth_method="client_secret_post")


def _supabase_handler(seen=None):
    """Mock do GoTrue: password/refresh → sessão; signup → conta; /user → id; logout → 204."""
    def handler(req: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(req)
        import json
        path = req.url.path
        if path == "/auth/v1/token":
            grant = req.url.params.get("grant_type")
            if grant == "password":
                body = json.loads(req.content or b"{}")
                if body.get("password") == "correct":
                    return httpx.Response(200, json={"access_token": "JWT-access",
                                                     "refresh_token": "RT-1", "expires_in": 3600})
                return httpx.Response(400, json={"error": "invalid_grant"})
            if grant == "refresh_token":
                return httpx.Response(200, json={"access_token": "JWT-access-2",
                                                 "refresh_token": "RT-2", "expires_in": 3600})
            if grant == "pkce":                         # login hospedado: troca auth_code+verifier
                body = json.loads(req.content or b"{}")
                if body.get("auth_code") == "good-code" and body.get("code_verifier"):
                    return httpx.Response(200, json={"access_token": "JWT-hosted",
                                                     "refresh_token": "RT-h", "expires_in": 3600})
                return httpx.Response(400, json={"error": "invalid_grant"})
        if path == "/auth/v1/signup":
            body = json.loads(req.content or b"{}")
            if body.get("email") == "exists@b.c":
                return httpx.Response(422, json={"msg": "User already registered"})
            if body.get("email") == "needsconfirm@b.c":
                return httpx.Response(200, json={"id": "u-new", "email": body["email"]})  # sem token
            return httpx.Response(200, json={"access_token": "JWT-new", "refresh_token": "RT-new",
                                             "expires_in": 3600})  # auto-confirm → sessão
        if path == "/auth/v1/user":
            if req.headers.get("authorization") == "Bearer JWT-access":
                return httpx.Response(200, json={"id": "user-9", "email": "a@b.c"})
            return httpx.Response(401, json={"msg": "bad"})
        if path == "/auth/v1/logout":
            return httpx.Response(204)
        return httpx.Response(404)
    return handler


def _as(seen=None):
    return SupabaseAuthServer(supabase_url="https://proj.supabase.co", supabase_key="anon",
                              public_url="https://mcp.example", transport=httpx.MockTransport(_supabase_handler(seen)))


def _as_hosted(seen=None):
    """AS no modo HOSPEDADO (login social via Supabase, sem ROPC)."""
    return SupabaseAuthServer(supabase_url="https://proj.supabase.co", supabase_key="anon",
                              public_url="https://mcp.example", login_provider="github",
                              transport=httpx.MockTransport(_supabase_handler(seen)))


def _client_store_handler(db):
    """Mock stateful da tabela lifeline_oauth_clients via PostgREST (GET select / POST upsert)."""
    def handler(req: httpx.Request) -> httpx.Response:
        import json
        if req.url.path == "/rest/v1/lifeline_oauth_clients":
            if req.method == "POST":
                body = json.loads(req.content or b"{}")
                db[body["client_id"]] = body["client_info"]
                return httpx.Response(201)
            if req.method == "GET":
                cid = req.url.params.get("client_id", "").replace("eq.", "")
                if cid in db:
                    return httpx.Response(200, json=[{"client_info": db[cid]}])
                return httpx.Response(200, json=[])
        return httpx.Response(404)
    return handler


class _Form:
    """Mini Request com .form() — evita depender de python-multipart no teste."""
    def __init__(self, data, query=None):
        self._data = data
        self.query_params = query or {}

    async def form(self):
        return self._data


class TestDCR(unittest.IsolatedAsyncioTestCase):
    async def test_register_and_get_client(self):
        a = _as()
        c = _client()
        self.assertIsNone(await a.get_client("c-1"))
        await a.register_client(c)
        got = await a.get_client("c-1")
        self.assertEqual(got.client_id, "c-1")


class TestAuthorizeFlow(unittest.IsolatedAsyncioTestCase):
    async def test_authorize_returns_login_redirect_with_ticket(self):
        a = _as()
        _v, challenge = _pkce()
        params = AuthorizationParams(state="xyz", scopes=[], code_challenge=challenge,
                                     redirect_uri="https://conector.example/callback",
                                     redirect_uri_provided_explicitly=True, resource=None)
        url = await a.authorize(_client(), params)
        self.assertTrue(url.startswith("https://mcp.example/oauth/login?ticket="))
        self.assertEqual(len(a._tickets), 1)               # guardou os params sob o ticket

    async def test_login_mints_code_and_redirects_to_connector(self):
        a = _as()
        _v, challenge = _pkce()
        params = AuthorizationParams(state="st-1", scopes=[], code_challenge=challenge,
                                     redirect_uri="https://conector.example/callback",
                                     redirect_uri_provided_explicitly=True, resource=None)
        url = await a.authorize(_client(), params)
        ticket = url.split("ticket=")[1]

        resp = await a.login_post(_Form({"ticket": ticket, "email": "a@b.c", "password": "correct"}))
        self.assertEqual(resp.status_code, 302)
        loc = resp.headers["location"]
        self.assertIn("https://conector.example/callback", loc)
        self.assertIn("state=st-1", loc)
        self.assertIn("code=", loc)
        self.assertEqual(a._tickets, {})                   # ticket consumido (one-time)
        self.assertEqual(len(a._codes), 1)                 # code emitido

    async def test_login_wrong_password_is_401_no_code(self):
        a = _as()
        _v, challenge = _pkce()
        url = await a.authorize(_client(), AuthorizationParams(
            state="s", scopes=[], code_challenge=challenge,
            redirect_uri="https://conector.example/callback",
            redirect_uri_provided_explicitly=True, resource=None))
        ticket = url.split("ticket=")[1]
        resp = await a.login_post(_Form({"ticket": ticket, "email": "a@b.c", "password": "WRONG"}))
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(a._codes, {})                     # nenhum code sem auth válida

    async def test_login_bad_ticket_is_400(self):
        a = _as()
        resp = await a.login_post(_Form({"ticket": "nope", "email": "a@b.c", "password": "correct"}))
        self.assertEqual(resp.status_code, 400)


class TestSignup(unittest.IsolatedAsyncioTestCase):
    """Primeiro acesso: criar conta no Supabase pelo mesmo form (sem isto o 1º usuário trava)."""

    async def _ticket(self, a):
        _v, challenge = _pkce()
        url = await a.authorize(_client(), AuthorizationParams(
            state="s", scopes=[], code_challenge=challenge,
            redirect_uri="https://conector.example/callback",
            redirect_uri_provided_explicitly=True, resource=None))
        return url.split("ticket=")[1]

    async def test_signup_autoconfirm_mints_code(self):
        a = _as()
        ticket = await self._ticket(a)
        resp = await a.login_post(_Form({"ticket": ticket, "email": "novo@b.c",
                                         "password": "x", "signup": "1"}))
        self.assertEqual(resp.status_code, 302)               # conta criada + logada inline
        self.assertIn("code=", resp.headers["location"])
        self.assertEqual(len(a._codes), 1)

    async def test_signup_needs_email_confirmation_shows_message(self):
        a = _as()
        ticket = await self._ticket(a)
        resp = await a.login_post(_Form({"ticket": ticket, "email": "needsconfirm@b.c",
                                         "password": "x", "signup": "1"}))
        self.assertEqual(resp.status_code, 400)
        self.assertIn("confirme pelo email", resp.body.decode())
        self.assertEqual(a._codes, {})                        # sem sessão → sem code

    async def test_signup_existing_user_errors(self):
        a = _as()
        ticket = await self._ticket(a)
        resp = await a.login_post(_Form({"ticket": ticket, "email": "exists@b.c",
                                         "password": "x", "signup": "1"}))
        self.assertEqual(resp.status_code, 400)
        self.assertIn("já exista", resp.body.decode())


class TestTokenExchange(unittest.IsolatedAsyncioTestCase):
    async def _mint(self, a, client):
        _v, challenge = _pkce()
        url = await a.authorize(client, AuthorizationParams(
            state="s", scopes=["lifeline"], code_challenge=challenge,
            redirect_uri="https://conector.example/callback",
            redirect_uri_provided_explicitly=True, resource=None))
        ticket = url.split("ticket=")[1]
        resp = await a.login_post(_Form({"ticket": ticket, "email": "a@b.c", "password": "correct"}))
        return resp.headers["location"].split("code=")[1].split("&")[0]

    async def test_load_and_exchange_code_returns_supabase_jwt(self):
        a = _as()
        client = _client()
        code = await self._mint(a, client)
        ac = await a.load_authorization_code(client, code)
        self.assertIsNotNone(ac)
        token = await a.exchange_authorization_code(client, ac)
        self.assertEqual(token.access_token, "JWT-access")  # o access token É o JWT do Supabase
        self.assertEqual(token.refresh_token, "RT-1")

    async def test_code_is_one_time(self):
        a = _as()
        client = _client()
        code = await self._mint(a, client)
        ac = await a.load_authorization_code(client, code)
        await a.exchange_authorization_code(client, ac)
        with self.assertRaises(TokenError):                 # segunda troca → recusada
            await a.exchange_authorization_code(client, ac)
        self.assertIsNone(await a.load_authorization_code(client, code))  # e some do store

    async def test_code_bound_to_client(self):
        a = _as()
        code = await self._mint(a, _client("c-1"))
        other = _client("c-2")
        self.assertIsNone(await a.load_authorization_code(other, code))   # outro client não usa

    async def test_expired_code_rejected(self):
        a = SupabaseAuthServer(supabase_url="https://proj.supabase.co", supabase_key="anon",
                               public_url="https://mcp.example", code_ttl=-1,  # já nasce expirado
                               transport=httpx.MockTransport(_supabase_handler()))
        client = _client()
        code = await self._mint(a, client)
        self.assertIsNone(await a.load_authorization_code(client, code))


class TestRefreshAndIntrospect(unittest.IsolatedAsyncioTestCase):
    async def test_refresh_delegates_to_supabase(self):
        a = _as()
        client = _client()
        rt = await a.load_refresh_token(client, "RT-1")
        self.assertIsNotNone(rt)
        token = await a.exchange_refresh_token(client, rt, ["lifeline"])
        self.assertEqual(token.access_token, "JWT-access-2")  # novo JWT do Supabase

    async def test_load_access_token_validates_against_supabase(self):
        a = _as()
        at = await a.load_access_token("JWT-access")
        self.assertIsNotNone(at)
        self.assertEqual(at.client_id, "user-9")              # escopa a RLS por usuário
        self.assertIsNone(await a.load_access_token("garbage"))  # inválido → None (401)

    async def test_revoke_is_best_effort(self):
        a = _as()
        rt = await a.load_refresh_token(_client(), "RT-1")
        await a.revoke_token(rt)                               # não levanta (logout best-effort)


class TestEndToEndASGI(unittest.IsolatedAsyncioTestCase):
    """O baile OAuth COMPLETO pelas rotas HTTP reais (DCR→authorize→login→token), Supabase
    mockado. É o mais perto do handshake do claude.ai sem um conector ao vivo — prova o fio
    inteiro: PKCE S256, match de redirect, code one-time, token = JWT do Supabase."""

    def _server(self):
        from mcp.server.fastmcp import FastMCP
        from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions
        from mcp.server.transport_security import TransportSecuritySettings
        provider = _as()
        server = FastMCP(
            "Lifeline", auth_server_provider=provider,
            auth=AuthSettings(issuer_url="https://mcp.example", resource_server_url="https://mcp.example",
                              required_scopes=[], client_registration_options=ClientRegistrationOptions(enabled=True)),
            transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False))
        provider.register_login_routes(server)
        return server

    async def test_full_oauth_dance(self):
        app = self._server().sse_app()
        tr = httpx.ASGITransport(app=app)
        verifier, challenge = _pkce()
        redirect = "https://conector.example/callback"
        async with httpx.AsyncClient(transport=tr, base_url="https://mcp.example",
                                     follow_redirects=False) as c:
            # 1) DCR — o conector se registra (cliente público + PKCE, como o claude.ai)
            reg = await c.post("/register", json={
                "redirect_uris": [redirect], "token_endpoint_auth_method": "none",
                "grant_types": ["authorization_code", "refresh_token"], "response_types": ["code"]})
            self.assertEqual(reg.status_code, 201, reg.text)
            client_id = reg.json()["client_id"]

            # 2) /authorize → 302 para o nosso /oauth/login (com ticket)
            authz = await c.get("/authorize", params={
                "response_type": "code", "client_id": client_id, "redirect_uri": redirect,
                "code_challenge": challenge, "code_challenge_method": "S256", "state": "st-9"})
            self.assertEqual(authz.status_code, 302, authz.text)
            self.assertIn("/oauth/login", authz.headers["location"])
            ticket = authz.headers["location"].split("ticket=")[1]

            # 3) /oauth/login (delega ao Supabase) → 302 ao redirect_uri do conector com code+state
            login = await c.post("/oauth/login",
                                 data={"ticket": ticket, "email": "a@b.c", "password": "correct"})
            self.assertEqual(login.status_code, 302, login.text)
            cb = login.headers["location"]
            self.assertIn(redirect, cb)
            self.assertIn("state=st-9", cb)
            code = cb.split("code=")[1].split("&")[0]

            # 4) /token — PKCE verificado pelo SDK → access_token = JWT do Supabase
            tok = await c.post("/token", data={
                "grant_type": "authorization_code", "code": code, "redirect_uri": redirect,
                "client_id": client_id, "code_verifier": verifier})
            self.assertEqual(tok.status_code, 200, tok.text)
            self.assertEqual(tok.json()["access_token"], "JWT-access")

    async def test_token_rejects_wrong_pkce_verifier(self):
        app = self._server().sse_app()
        tr = httpx.ASGITransport(app=app)
        _verifier, challenge = _pkce()
        redirect = "https://conector.example/callback"
        async with httpx.AsyncClient(transport=tr, base_url="https://mcp.example",
                                     follow_redirects=False) as c:
            reg = await c.post("/register", json={
                "redirect_uris": [redirect], "token_endpoint_auth_method": "none",
                "grant_types": ["authorization_code", "refresh_token"], "response_types": ["code"]})
            self.assertEqual(reg.status_code, 201, reg.text)
            client_id = reg.json()["client_id"]
            authz = await c.get("/authorize", params={
                "response_type": "code", "client_id": client_id, "redirect_uri": redirect,
                "code_challenge": challenge, "code_challenge_method": "S256", "state": "s"})
            ticket = authz.headers["location"].split("ticket=")[1]
            login = await c.post("/oauth/login",
                                 data={"ticket": ticket, "email": "a@b.c", "password": "correct"})
            code = login.headers["location"].split("code=")[1].split("&")[0]
            tok = await c.post("/token", data={
                "grant_type": "authorization_code", "code": code, "redirect_uri": redirect,
                "client_id": client_id, "code_verifier": "verifier-ERRADO-nao-bate-com-o-challenge"})
            self.assertEqual(tok.status_code, 400)            # PKCE falhou → invalid_grant
            self.assertIn("invalid_grant", tok.text)


class TestRobustness(unittest.IsolatedAsyncioTestCase):
    """Incidente do deploy: SUPABASE_URL sem https:// → httpx UnsupportedProtocol → 500 cru
    no login. Conserto: normaliza a URL na entrada + trata/loga toda falha do Supabase."""

    def test_clean_url_adds_scheme_and_trims(self):
        from lifeline.cloud import clean_url
        self.assertEqual(clean_url("rzp.supabase.co"), "https://rzp.supabase.co")     # sem esquema
        self.assertEqual(clean_url("  https://rzp.supabase.co/  "), "https://rzp.supabase.co")  # espaço+barra
        self.assertEqual(clean_url("http://localhost:8000"), "http://localhost:8000")  # http preservado

    def test_schemeless_url_is_normalized(self):
        a = SupabaseAuthServer(supabase_url="rzp.supabase.co", supabase_key=" anon ",
                               public_url="lifeline.example", transport=httpx.MockTransport(_supabase_handler()))
        self.assertEqual(a.url, "https://rzp.supabase.co")          # https:// garantido
        self.assertEqual(a.key, "anon")                             # key trimada
        self.assertEqual(a.public_url, "https://lifeline.example")

    async def test_supabase_network_error_is_graceful_not_500(self):
        def boom(req):
            raise httpx.ConnectError("rede caiu")
        a = SupabaseAuthServer(supabase_url="https://x.supabase.co", supabase_key="k",
                               public_url="https://mcp.example", transport=httpx.MockTransport(boom))
        self.assertIsNone(await a._supabase_token("password", {"email": "a", "password": "b"}))  # None, não estoura
        sess, msg = await a._supabase_signup("a@b.c", "x")
        self.assertIsNone(sess)
        self.assertIn("indisponível", msg)                          # mensagem clara
        self.assertIsNone(await a.load_access_token("tok"))         # introspecção também graciosa

    async def test_login_post_never_raises_bare_500(self):
        # ticket válido mas o Supabase estoura → login devolve o form com erro, status definido
        def boom(req):
            raise httpx.ConnectError("rede caiu")
        a = SupabaseAuthServer(supabase_url="https://x.supabase.co", supabase_key="k",
                               public_url="https://mcp.example", transport=httpx.MockTransport(boom))
        _v, challenge = _pkce()
        url = await a.authorize(_client(), AuthorizationParams(
            state="s", scopes=[], code_challenge=challenge,
            redirect_uri="https://conector.example/callback",
            redirect_uri_provided_explicitly=True, resource=None))
        ticket = url.split("ticket=")[1]
        resp = await a.login_post(_Form({"ticket": ticket, "email": "a@b.c", "password": "x"}))
        self.assertIn(resp.status_code, (400, 401))                 # erro tratado (credencial inválida), não 500
        self.assertEqual(a._codes, {})


class TestHostedLogin(unittest.IsolatedAsyncioTestCase):
    """Endurecimento: com provider social configurado, /oauth/login redireciona ao login
    HOSPEDADO do Supabase (a senha não toca nosso servidor) e /oauth/callback troca o code
    por sessão (grant_type=pkce). É o caminho de produção que substitui o ROPC."""

    async def _ticket(self, a):
        _v, challenge = _pkce()
        url = await a.authorize(_client(), AuthorizationParams(
            state="st-h", scopes=["lifeline"], code_challenge=challenge,
            redirect_uri="https://conector.example/callback",
            redirect_uri_provided_explicitly=True, resource=None))
        return url.split("ticket=")[1]

    async def test_login_get_redirects_to_supabase_social(self):
        a = _as_hosted()
        ticket = await self._ticket(a)
        resp = await a.login_get(_Form({}, query={"ticket": ticket}))
        self.assertEqual(resp.status_code, 302)
        loc = resp.headers["location"]
        self.assertTrue(loc.startswith("https://proj.supabase.co/auth/v1/authorize?provider=github"), loc)
        self.assertIn("code_challenge=", loc)
        self.assertIn("code_challenge_method=s256", loc)
        self.assertIn("oauth%2Fcallback", loc)            # redirect_to (encoded) volta pro callback
        self.assertIn(ticket, a._pkce)                    # verifier guardado p/ a troca

    async def test_login_get_bad_ticket_is_400(self):
        a = _as_hosted()
        resp = await a.login_get(_Form({}, query={"ticket": "nope"}))
        self.assertEqual(resp.status_code, 400)

    async def test_callback_exchanges_code_and_mints_token(self):
        a = _as_hosted()
        ticket = await self._ticket(a)
        await a.login_get(_Form({}, query={"ticket": ticket}))      # popula _pkce
        resp = await a.oauth_callback(_Form({}, query={"ticket": ticket, "code": "good-code"}))
        self.assertEqual(resp.status_code, 302)
        loc = resp.headers["location"]
        self.assertIn("https://conector.example/callback", loc)
        self.assertIn("state=st-h", loc)
        self.assertEqual(a._tickets, {})                  # ticket consumido
        self.assertNotIn(ticket, a._pkce)                 # verifier limpo
        code = loc.split("code=")[1].split("&")[0]
        ac = await a.load_authorization_code(_client(), code)
        tok = await a.exchange_authorization_code(_client(), ac)
        self.assertEqual(tok.access_token, "JWT-hosted")  # access token = JWT do Supabase (via pkce)

    async def test_callback_provider_error_is_400_no_code(self):
        a = _as_hosted()
        ticket = await self._ticket(a)
        await a.login_get(_Form({}, query={"ticket": ticket}))
        resp = await a.oauth_callback(_Form({}, query={"ticket": ticket, "error": "access_denied"}))
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(a._codes, {})                    # login negado → nenhum code
        self.assertNotIn(ticket, a._pkce)

    async def test_callback_bad_ticket_is_400(self):
        a = _as_hosted()
        resp = await a.oauth_callback(_Form({}, query={"ticket": "nope", "code": "x"}))
        self.assertEqual(resp.status_code, 400)

    async def test_no_provider_falls_back_to_password_form(self):
        a = _as()                                         # sem provider → form (dev/CLI)
        resp = await a.login_get(_Form({}, query={"ticket": "t"}))
        self.assertEqual(resp.status_code, 200)
        self.assertIn("password", resp.body.decode())


class TestPersistentClientStore(unittest.IsolatedAsyncioTestCase):
    """Persistência DCR: SupabaseClientStore grava/lê na tabela; um AS com esse store recupera
    o client mesmo numa instância NOVA (cache vazio) — prova que sobrevive a restart/réplica."""

    async def test_supabase_client_store_roundtrip(self):
        db = {}
        store = SupabaseClientStore(url="https://proj.supabase.co", service_key="svc",
                                    transport=httpx.MockTransport(_client_store_handler(db)))
        self.assertIsNone(await store.get("c-1"))         # vazio
        await store.put(_client("c-1"))
        self.assertIn("c-1", db)                          # persistiu na "tabela"
        got = await store.get("c-1")
        self.assertEqual(got.client_id, "c-1")

    async def test_default_store_is_in_memory(self):
        a = _as()
        self.assertIsInstance(a._store, InMemoryClientStore)

    async def test_as_with_persistent_store_survives_new_instance(self):
        db = {}

        def mk_as():
            store = SupabaseClientStore(url="https://proj.supabase.co", service_key="svc",
                                        transport=httpx.MockTransport(_client_store_handler(db)))
            return SupabaseAuthServer(supabase_url="https://proj.supabase.co", supabase_key="anon",
                                      public_url="https://mcp.example", client_store=store,
                                      transport=httpx.MockTransport(_supabase_handler()))

        a1 = mk_as()
        await a1.register_client(_client("persist-1"))
        a2 = mk_as()                                      # "novo processo": _client_cache vazio
        got = await a2.get_client("persist-1")            # vem da tabela, não da memória
        self.assertIsNotNone(got)
        self.assertEqual(got.client_id, "persist-1")


class TestBuildRemoteAS(unittest.TestCase):
    def test_oauth_as_mounts_dcr_and_token_endpoints(self):
        self.addCleanup(lambda: cli._STORE.update(kind="sqlite", line="ledger"))
        env = {"LIFELINE_OAUTH_AS": "1", "LIFELINE_STORE": "supabase",
               "SUPABASE_URL": "https://proj.supabase.co", "SUPABASE_KEY": "anon",
               "LIFELINE_MCP_PUBLIC_URL": "https://mcp.example"}
        with mock.patch.dict(os.environ, env):
            srv._configure()
            server = srv._build_remote()
        self.assertIsNotNone(server.settings.auth)
        paths = {getattr(r, "path", "") for r in server.sse_app().routes}
        # DCR + authorize + token + metadata + nosso login
        self.assertIn("/register", paths)
        self.assertIn("/authorize", paths)
        self.assertIn("/token", paths)
        self.assertIn("/oauth/login", paths)
        self.assertIn("/oauth/callback", paths)            # modo hospedado
        self.assertTrue(any("oauth-authorization-server" in p for p in paths), paths)


if __name__ == "__main__":
    unittest.main(verbosity=2)
