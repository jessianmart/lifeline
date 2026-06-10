"""Contrato MCP: o loop sem humano precisa de leitura (resource) E escrita (tools).
Cobre também a escolha de backend (local/remoto) e que a escrita continua HITL."""
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx                         # noqa: E402
import lifeline.mcp_server as srv     # noqa: E402
from lifeline import cli             # noqa: E402
from lifeline.mcp_server import mcp  # noqa: E402


class TestMCPContract(unittest.IsolatedAsyncioTestCase):
    async def test_write_tools_registered(self):
        names = [t.name for t in await mcp.list_tools()]
        self.assertIn("lifeline_append", names)           # escrita: anexar
        self.assertIn("lifeline_recontextualize", names)  # escrita: supersede
        self.assertIn("lifeline_recall", names)           # leitura: relevância

    async def test_context_resource_registered(self):
        uris = [str(r.uri) for r in await mcp.list_resources()]
        uris += [t.uriTemplate for t in await mcp.list_resource_templates()]
        self.assertTrue(any("lifeline://project/context" in u for u in uris))

    def test_healthz_route_registered(self):
        # health check (Render/Railway) + checagem no navegador → GET /healthz deve existir
        paths = {getattr(r, "path", "") for r in mcp.streamable_http_app().routes}
        self.assertIn("/healthz", paths)

    def test_instructions_cover_bootstrap(self):
        # AI-first: a IA que conecta a uma line vazia precisa saber fazer o checkpoint HITL
        text = srv._INSTRUCTIONS
        self.assertIn("BOOTSTRAP", text.upper())
        self.assertIn("granulares", text.lower())          # entradas granulares (não bloco único)
        self.assertIn("nunca infira", text.lower())        # guardrail: não inferir do código


class TestMCPBackendAndHITL(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.addCleanup(lambda: cli._STORE.update(kind="sqlite", line="ledger"))

    def test_configure_selects_backend_from_env(self):
        with mock.patch.dict(os.environ, {"LIFELINE_STORE": "supabase", "LIFELINE_LINE": "research"}):
            srv._configure()
        self.assertEqual(cli._STORE["kind"], "supabase")    # modo nuvem (remoto) escolhido por env
        self.assertEqual(cli._STORE["line"], "research")

    def test_configure_defaults_to_sqlite(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            srv._configure()
        self.assertEqual(cli._STORE["kind"], "sqlite")      # local por padrão (sem regressão)

    async def test_append_tool_is_hitl(self):
        # a tool de escrita PROPÕE (fila pendente), NÃO commita direto na line (HITL)
        cli._STORE.update(kind="sqlite", line="ledger")
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        self.addCleanup(setattr, srv, "_DB", srv._DB)        # restaura o _DB original
        db = os.path.join(d, ".lifeline", "ledger.db")
        srv._DB = db
        msg = await srv.lifeline_append("decision", "usar gRPC", "porque escala")
        self.assertIn("PENDENTE", msg)
        self.assertEqual(len(await cli.cmd_review(db)), 1)   # entrou na fila…
        _, n, _t, _d = await cli.cmd_verify(db)
        self.assertEqual(n, 0)                                # …e NÃO na line (0 entradas seladas)

    async def test_handlers_read_the_line(self):
        # executa os handlers de LEITURA (project_context, lifeline_recall) contra um store real
        from lifeline.store import SQLiteEventStore
        from lifeline.entry import Entry
        cli._STORE.update(kind="sqlite", line="ledger")
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        self.addCleanup(setattr, srv, "_DB", srv._DB)
        db = os.path.join(d, ".lifeline", "ledger.db")
        os.makedirs(os.path.dirname(db))
        srv._DB = db
        s = SQLiteEventStore(db)
        await s.initialize()
        await s.append(Entry(kind="bootstrap", author="a", summary="Funda Z", body="why"))
        await s.append(Entry(kind="decision", author="a", summary="use SQLite", body="simple"))

        ctx = await srv.project_context()                     # resource montado
        self.assertIn("Funda Z", ctx)
        self.assertIn("use SQLite", ctx)
        self.assertIn("use SQLite", await srv.lifeline_recall("sqlite"))         # recall acha
        self.assertIn("Nada relevante", await srv.lifeline_recall("zzqxyznada"))  # sem match → mensagem vazia


class TestOAuthResourceServer(unittest.IsolatedAsyncioTestCase):
    def _verifier(self, handler):
        return srv.SupabaseTokenVerifier(url="https://proj.supabase.co", key="anon",
                                         transport=httpx.MockTransport(handler))

    async def test_valid_token_returns_access_token(self):
        seen = []

        def handler(req):
            seen.append(req)
            return httpx.Response(200, json={"id": "user-123", "email": "a@b.c"})

        at = await self._verifier(handler).verify_token("jwt-xyz")
        self.assertIsNotNone(at)
        self.assertEqual(at.token, "jwt-xyz")        # carrega o JWT p/ escopar a RLS por usuário
        self.assertEqual(at.client_id, "user-123")   # user id do Supabase
        req = seen[0]
        self.assertTrue(str(req.url).endswith("/auth/v1/user"))
        self.assertEqual(req.headers["apikey"], "anon")
        self.assertEqual(req.headers["authorization"], "Bearer jwt-xyz")

    async def test_invalid_token_returns_none(self):
        at = await self._verifier(lambda req: httpx.Response(401, json={"msg": "bad"})).verify_token("nope")
        self.assertIsNone(at)                         # 401 → rejeitado

    async def test_missing_config_returns_none(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            v = srv.SupabaseTokenVerifier()           # sem url/key
        self.assertIsNone(await v.verify_token("whatever"))

    def test_build_remote_with_oauth_serves_metadata(self):
        self.addCleanup(lambda: cli._STORE.update(kind="sqlite", line="ledger"))
        env = {"LIFELINE_OAUTH": "1", "LIFELINE_STORE": "supabase",
               "SUPABASE_URL": "https://proj.supabase.co", "SUPABASE_KEY": "anon"}
        with mock.patch.dict(os.environ, env):
            srv._configure()
            server = srv._build_remote()
        self.assertIsNotNone(server.settings.auth)    # virou Resource Server
        paths = {getattr(r, "path", "") for r in server.sse_app().routes}
        self.assertTrue(any("oauth-protected-resource" in p for p in paths), paths)  # discovery

    def test_build_remote_without_oauth_is_authless(self):
        self.addCleanup(lambda: cli._STORE.update(kind="sqlite", line="ledger"))
        with mock.patch.dict(os.environ, {}, clear=True):
            srv._configure()
            server = srv._build_remote()
        self.assertIsNone(server.settings.auth)       # sem OAuth → authless

    def test_transport_security_allows_configured_host(self):
        with mock.patch.dict(os.environ, {"LIFELINE_MCP_ALLOWED_HOSTS": "x.trycloudflare.com,meu.app"}):
            ts = srv._transport_security()
        self.assertTrue(ts.enable_dns_rebinding_protection)   # proteção ON com lista
        self.assertIn("x.trycloudflare.com", ts.allowed_hosts)
        self.assertIn("meu.app:*", ts.allowed_hosts)

    def test_transport_security_default_disables_protection(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            ts = srv._transport_security()
        self.assertFalse(ts.enable_dns_rebinding_protection)  # túnel/proxy: host variável → libera


if __name__ == "__main__":
    unittest.main(verbosity=2)
