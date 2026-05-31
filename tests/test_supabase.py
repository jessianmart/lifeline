"""Prova o adapter Supabase em duas camadas (segue #0039 — sem overclaim):

1. WIRE (mockado, roda sempre): httpx.MockTransport intercepta as requests. Provam que
   montamos POST/GET certos (URL, headers apikey+Bearer, Prefer, filtros) e que parseamos
   as respostas em Entry. NÃO provam o contrato do Postgres/RLS — isso é o nível 2.
2. CONTRATO (live, skip-gated): round-trip real + prova que a RLS é append-only. Só roda
   quando SUPABASE_URL/KEY estão no ambiente (a outra sessão roda com as creds do projeto).
"""
import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx  # noqa: E402

from lifeline.entry import Entry            # noqa: E402
from lifeline.cloud import SupabaseEventStore, SupabaseStagingStore  # noqa: E402


def _store(handler, line="ledger"):
    """SupabaseEventStore com transporte mockado — sem rede, sem banco."""
    return SupabaseEventStore(line=line, url="https://proj.supabase.co",
                              key="test-key", transport=httpx.MockTransport(handler))


def _staging(handler, line="ledger"):
    """SupabaseStagingStore com transporte mockado."""
    return SupabaseStagingStore(line=line, url="https://proj.supabase.co",
                                key="proj-anon", token="user-jwt", transport=httpx.MockTransport(handler))


class TestSupabaseWire(unittest.IsolatedAsyncioTestCase):
    async def test_append_builds_request(self):
        seen = []

        def handler(req):
            seen.append(req)
            return httpx.Response(201)  # inserido

        e = Entry(kind="decision", author="a", summary="usar gRPC", body="porque escala")
        self.assertTrue(await _store(handler).append(e))
        req = seen[0]
        self.assertEqual(req.method, "POST")
        self.assertTrue(str(req.url).endswith("/rest/v1/lifeline_entries"))
        self.assertEqual(req.headers["apikey"], "test-key")
        self.assertEqual(req.headers["authorization"], "Bearer test-key")
        self.assertIn("ignore-duplicates", req.headers["prefer"])  # idempotência no servidor
        body = json.loads(req.content)
        self.assertEqual(body["id"], e.id)
        self.assertEqual(body["line"], "ledger")
        self.assertEqual(body["payload"]["summary"], "usar gRPC")  # Entry inteiro vai no payload

    async def test_apikey_and_bearer_are_separate_values(self):
        # fix do gateway (#0042): apikey = chave do PROJETO; Bearer = token do USUÁRIO (RLS).
        seen = []

        def handler(req):
            seen.append(req)
            return httpx.Response(201)

        store = SupabaseEventStore(line="ledger", url="https://proj.supabase.co",
                                   key="proj-anon", token="user-jwt",
                                   transport=httpx.MockTransport(handler))
        await store.append(Entry(kind="note", author="a", summary="s"))
        self.assertEqual(seen[0].headers["apikey"], "proj-anon")              # chave do projeto
        self.assertEqual(seen[0].headers["authorization"], "Bearer user-jwt")  # JWT do usuário

    def test_token_falls_back_to_apikey_when_absent(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            s = SupabaseEventStore(url="https://p.supabase.co", key="only-key")
        self.assertEqual(s.token, "only-key")  # sem token → Bearer usa o apikey (anon/service_role)

    def test_token_read_from_env_when_key_not_explicit(self):
        env = {"SUPABASE_URL": "https://p.supabase.co", "SUPABASE_KEY": "anon", "SUPABASE_TOKEN": "jwt"}
        with mock.patch.dict(os.environ, env, clear=True):
            s = SupabaseEventStore(line="ledger")
        self.assertEqual((s.key, s.token), ("anon", "jwt"))  # dois valores separados via env

    async def test_append_idempotent_status_codes(self):
        e = Entry(kind="note", author="a", summary="dup")
        for code in (200, 201, 204):  # duplicado ignorado (200/204) também é sucesso
            self.assertTrue(await _store(lambda req, c=code: httpx.Response(c)).append(e))
        self.assertFalse(await _store(lambda req: httpx.Response(409)).append(e))  # erro real → False

    async def test_get_parses_payload_and_filters(self):
        e = Entry(kind="decision", author="a", summary="x", body="why")
        payload = json.loads(e.model_dump_json())
        seen = []

        def handler(req):
            seen.append(req)
            return httpx.Response(200, json=[{"payload": payload}])

        got = await _store(handler).get(e.id)
        self.assertIsNotNone(got)
        self.assertEqual(got.id, e.id)
        self.assertTrue(got.verify())  # sobreviveu ao roundtrip e o id ainda bate
        req = seen[0]
        self.assertEqual(req.url.params["id"], f"eq.{e.id}")
        self.assertEqual(req.url.params["line"], "eq.ledger")
        self.assertEqual(req.url.params["select"], "payload")

    async def test_get_missing_returns_none(self):
        self.assertIsNone(await _store(lambda req: httpx.Response(200, json=[])).get("nope"))

    async def test_stream_orders_by_seq(self):
        es = [Entry(kind="note", author="a", summary=f"s{i}") for i in range(3)]
        seen = []

        def handler(req):
            seen.append(req)
            return httpx.Response(200, json=[{"payload": json.loads(e.model_dump_json())} for e in es])

        out = [x async for x in _store(handler).stream()]
        self.assertEqual([x.summary for x in out], ["s0", "s1", "s2"])
        self.assertEqual(seen[0].url.params["order"], "seq.asc")  # ordem causal

    async def test_children_uses_jsonb_contains(self):
        parent = Entry(kind="note", author="a", summary="p")
        child = Entry(kind="note", author="a", summary="c", parents=[parent.id])
        seen = []

        def handler(req):
            seen.append(req)
            return httpx.Response(200, json=[{"payload": json.loads(child.model_dump_json())}])

        kids = await _store(handler).children(parent.id)
        self.assertEqual([k.id for k in kids], [child.id])
        self.assertEqual(seen[0].url.params["parents"], f'cs.["{parent.id}"]')

    def test_missing_env_raises_clear_error(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError):
                SupabaseEventStore(line="ledger")  # sem url/key e sem env → recusa explícita


class TestCLIStoreGuard(unittest.TestCase):
    def test_local_only_commands_rejected_under_supabase(self):
        import lifeline.cli as cli
        # não vazar o store global para outros testes do processo
        self.addCleanup(lambda: cli._STORE.update(kind="sqlite", line="ledger"))
        # só git/glob-local são barrados; o HITL agora roda na nuvem (SupabaseStagingStore)
        extra = {"clone": ["a", "b"]}
        for cmd in ("push", "pull", "clone", "lines"):
            argv = ["--store", "supabase", cmd] + extra.get(cmd, [])
            self.assertEqual(cli.main(argv), 1, f"{cmd} deveria ser rejeitado no modo supabase")


class TestSupabaseStagingWire(unittest.IsolatedAsyncioTestCase):
    async def test_propose_posts_and_returns_pid(self):
        seen = []

        def handler(req):
            seen.append(req)
            return httpx.Response(201, json=[{"pid": 7}])

        pid = await _staging(handler).propose(
            kind="decision", summary="usar gRPC", body="porque escala",
            author="ia", agent="claude", provider="anthropic", model="m", parents=["abc"])
        self.assertEqual(pid, 7)
        req = seen[0]
        self.assertEqual(req.method, "POST")
        self.assertIn("return=representation", req.headers["prefer"])  # precisa do pid de volta
        body = json.loads(req.content)
        self.assertEqual(body["summary"], "usar gRPC")
        self.assertEqual(body["line"], "ledger")
        self.assertEqual(body["parents"], ["abc"])

    async def test_pending_filters_and_normalizes_parents(self):
        seen = []

        def handler(req):
            seen.append(req)
            return httpx.Response(200, json=[{"pid": 1, "status": "pending", "parents": ["p1"], "summary": "s"}])

        rows = await _staging(handler).pending()
        self.assertEqual(seen[0].url.params["status"], "eq.pending")
        self.assertEqual(seen[0].url.params["line"], "eq.ledger")
        # parents (jsonb→lista) normalizado p/ string JSON, igual ao SQLite → cmd_approve agnóstico
        self.assertEqual(rows[0]["parents"], '["p1"]')

    async def test_get_returns_none_when_absent(self):
        self.assertIsNone(await _staging(lambda req: httpx.Response(200, json=[])).get(99))

    async def test_set_status_patches_by_pid(self):
        seen = []

        def handler(req):
            seen.append(req)
            return httpx.Response(204)

        await _staging(handler).set_status(5, "approved")
        req = seen[0]
        self.assertEqual(req.method, "PATCH")
        self.assertEqual(req.url.params["pid"], "eq.5")
        self.assertEqual(json.loads(req.content)["status"], "approved")


@unittest.skipUnless(
    os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_KEY") and os.environ.get("SUPABASE_TOKEN"),
    "teste live: defina SUPABASE_URL, SUPABASE_KEY (apikey do projeto) e SUPABASE_TOKEN (JWT de usuário)",
)
class TestSupabaseLive(unittest.IsolatedAsyncioTestCase):
    """Roda na sessão com o projeto real. Usa a line 'lifeline_selftest' p/ não poluir 'ledger'."""

    LINE = "lifeline_selftest"

    async def test_round_trip(self):
        store = SupabaseEventStore(line=self.LINE)
        e = Entry(kind="note", author="selftest", summary="round-trip live", body="prova do contrato")
        await store.append(e)                       # idempotente: ok rodar de novo
        got = await store.get(e.id)
        self.assertIsNotNone(got, "append→get falhou (cheque schema/RLS/auth.uid())")
        self.assertEqual(got.id, e.id)
        self.assertIn(e.id, [x.id async for x in store.stream()])

    async def test_rls_is_append_only(self):
        """Sem policy de UPDATE/DELETE, a RLS deve NEGAR mutação (Leis #1 e #2 no banco)."""
        store = SupabaseEventStore(line=self.LINE)
        e = Entry(kind="note", author="selftest", summary="imutavel", body="nao deve mudar")
        await store.append(e)
        base = store.base
        params = {"line": f"eq.{self.LINE}", "id": f"eq.{e.id}"}
        async with httpx.AsyncClient(timeout=30) as c:
            upd = await c.patch(base, params=params, json={"summary": "hacked"},
                                headers=store._headers({"Prefer": "return=representation"}))
            dele = await c.request("DELETE", base, params=params,
                                   headers=store._headers({"Prefer": "return=representation"}))
        # negado = 4xx OU 200 com zero linhas afetadas
        for r in (upd, dele):
            denied = r.status_code >= 400 or (r.status_code == 200 and r.json() == [])
            self.assertTrue(denied, f"RLS deveria negar mutação; veio {r.status_code}: {r.text[:200]}")
        again = await store.get(e.id)               # e a entrada continua intacta
        self.assertEqual(again.summary, "imutavel")

    async def test_hitl_round_trip(self):
        """Fila HITL na nuvem: propose → aparece em pending → set_status sai de pending."""
        staging = SupabaseStagingStore(line=self.LINE)
        pid = await staging.propose(kind="note", summary="proposta live", body="curadoria",
                                    author="selftest", agent="x", provider="p", model="m")
        self.assertIn(pid, [p["pid"] for p in await staging.pending()])
        await staging.set_status(pid, "rejected")
        self.assertNotIn(pid, [p["pid"] for p in await staging.pending()])


if __name__ == "__main__":
    unittest.main(verbosity=2)
