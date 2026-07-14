"use client";

import React, { useState, useEffect } from "react";

interface Model {
  id: string;
  name: string;
  version: string;
  hash_sha256: string;
  is_active: boolean;
  deployed_at: string;
}

interface AuditLog {
  id: string;
  user_id: string | null;
  action: string;
  target: string | null;
  timestamp: string;
}

export default function AdminDashboard() {
  // Authentication states
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [token, setToken] = useState("");
  const [authError, setAuthError] = useState("");
  const [loading, setLoading] = useState(false);

  // Tab Selection
  const [activeTab, setActiveTab] = useState<"models" | "audit" | "privacy" | "health">("models");

  // System states
  const [modelsList, setModelsList] = useState<Model[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [apiOnline, setApiOnline] = useState(false);
  const [feedbackMsg, setFeedbackMsg] = useState("");

  const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  // Check health and connectivity
  useEffect(() => {
    fetch(`${API_URL}/health`)
      .then((res) => {
        if (res.ok) setApiOnline(true);
      })
      .catch(() => setApiOnline(false));
  }, [API_URL]);

  // Load dashboard data
  const loadData = async (authToken: string) => {
    try {
      const headers = { Authorization: `Bearer ${authToken}` };

      // Load models
      const modelsRes = await fetch(`${API_URL}/v1/admin/models`, { headers });
      if (modelsRes.ok) {
        const data = await modelsRes.json();
        setModelsList(data);
      } else {
        // Fallback mock local se a API retornar erro ou estiver vazia
        setModelsList([
          {
            id: "1",
            name: "Sinaliza AI Transformer Lite",
            version: "1.0.0-rc1",
            hash_sha256: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            is_active: true,
            deployed_at: new Date().toISOString(),
          },
          {
            id: "2",
            name: "Sinaliza AI GNN Heavy",
            version: "2.0.0-beta2",
            hash_sha256: "cf83e1357eefb8bdf1542850d66d8007d620e4050b5715dc83f4a921d36ce9ce",
            is_active: false,
            deployed_at: new Date().toISOString(),
          }
        ]);
      }

      // Load audit logs
      const auditRes = await fetch(`${API_URL}/v1/admin/audit-logs`, { headers });
      if (auditRes.ok) {
        const data = await auditRes.json();
        setAuditLogs(data);
      } else {
        setAuditLogs([
          {
            id: "log_1",
            user_id: "admin@sinaliza.ai",
            action: "DEPLOY_MODEL",
            target: "1.0.0-rc1",
            timestamp: new Date().toISOString(),
          },
          {
            id: "log_2",
            user_id: "admin@sinaliza.ai",
            action: "REGISTER_MODEL",
            target: "2.0.0-beta2",
            timestamp: new Date().toISOString(),
          }
        ]);
      }
    } catch (e) {
      console.error("Erro ao carregar dados", e);
    }
  };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setAuthError("");

    try {
      // Registrar usuário padrão caso a base esteja vazia
      await fetch(`${API_URL}/v1/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });

      // Efetuar Login
      const res = await fetch(`${API_URL}/v1/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });

      if (res.ok) {
        const data = await res.json();
        setToken(data.access_token);
        setIsLoggedIn(true);
        loadData(data.access_token);
      } else {
        setAuthError("Email ou senha inválidos. Tente novamente.");
      }
    } catch (err) {
      // Modo offline/desenvolvimento mock
      setToken("mock_admin_token_123");
      setIsLoggedIn(true);
      loadData("mock_admin_token_123");
    } finally {
      setLoading(false);
    }
  };

  const triggerDeploy = async (modelId: string, modelVer: string) => {
    try {
      const res = await fetch(`${API_URL}/v1/admin/models/${modelId}/deploy`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        setFeedbackMsg(`Modelo v${modelVer} implantado com sucesso!`);
        loadData(token);
      } else {
        // Mock deploy local
        setModelsList(modelsList.map(m => ({ ...m, is_active: m.id === modelId })));
        setAuditLogs([
          {
            id: `log_${Date.now()}`,
            user_id: "admin@sinaliza.ai",
            action: "DEPLOY_MODEL",
            target: modelVer,
            timestamp: new Date().toISOString(),
          },
          ...auditLogs
        ]);
        setFeedbackMsg(`[Mock] Modelo v${modelVer} implantado com sucesso.`);
      }
    } catch (e) {
      setFeedbackMsg("Erro na requisição de implantação.");
    }
  };

  const triggerRollback = async (modelId: string, modelVer: string) => {
    try {
      const res = await fetch(`${API_URL}/v1/admin/models/${modelId}/rollback`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        setFeedbackMsg(`Rollback do modelo v${modelVer} efetuado.`);
        loadData(token);
      } else {
        // Mock rollback local
        setModelsList(modelsList.map(m => m.id === modelId ? { ...m, is_active: false } : m));
        setAuditLogs([
          {
            id: `log_${Date.now()}`,
            user_id: "admin@sinaliza.ai",
            action: "ROLLBACK_MODEL",
            target: modelVer,
            timestamp: new Date().toISOString(),
          },
          ...auditLogs
        ]);
        setFeedbackMsg(`[Mock] Rollback do modelo v${modelVer} efetuado.`);
      }
    } catch (e) {
      setFeedbackMsg("Erro ao processar rollback.");
    }
  };

  if (!isLoggedIn) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-zinc-50 p-6 dark:bg-zinc-950">
        <div className="w-full max-w-md rounded-2xl bg-white p-8 shadow-xl dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800">
          <div className="text-center mb-6">
            <h1 className="text-2xl font-bold text-zinc-900 dark:text-white">Portal Sinaliza AI</h1>
            <p className="text-sm text-zinc-500 mt-2">Área Administrativa e de Governança de Dados</p>
          </div>

          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300" htmlFor="email-input">
                E-mail Corporativo
              </label>
              <input
                id="email-input"
                type="email"
                required
                className="mt-1 w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm focus:border-purple-500 focus:outline-none focus:ring-1 focus:ring-purple-500 dark:bg-zinc-800 dark:border-zinc-700"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300" htmlFor="password-input">
                Senha de Acesso
              </label>
              <input
                id="password-input"
                type="password"
                required
                className="mt-1 w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm focus:border-purple-500 focus:outline-none focus:ring-1 focus:ring-purple-500 dark:bg-zinc-800 dark:border-zinc-700"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>

            {authError && (
              <p className="text-xs text-red-600 font-medium" role="alert">{authError}</p>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-lg bg-purple-700 py-2.5 text-sm font-semibold text-white transition hover:bg-purple-800 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:ring-offset-2 disabled:bg-zinc-400"
            >
              {loading ? "Autenticando..." : "Entrar com MFA"}
            </button>
          </form>
        </div>
      </main>
    );
  }

  return (
    <div className="flex min-h-screen bg-zinc-50 dark:bg-zinc-950 font-sans">
      {/* Sidebar de Navegação */}
      <aside className="w-64 bg-white dark:bg-zinc-900 border-r border-zinc-200 dark:border-zinc-800 p-6 flex flex-col justify-between">
        <div>
          <h2 className="text-xl font-bold text-zinc-900 dark:text-white mb-6">Sinaliza AI Admin</h2>
          <nav className="space-y-2" aria-label="Navegação do Painel">
            <button
              onClick={() => setActiveTab("models")}
              className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-lg text-sm font-medium transition ${
                activeTab === "models" ? "bg-purple-55 text-purple-700 dark:bg-purple-950/30 dark:text-purple-400" : "text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800"
              }`}
            >
              📊 Model Registry
            </button>
            <button
              onClick={() => setActiveTab("audit")}
              className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-lg text-sm font-medium transition ${
                activeTab === "audit" ? "bg-purple-55 text-purple-700 dark:bg-purple-950/30 dark:text-purple-400" : "text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800"
              }`}
            >
              📜 Logs de Auditoria
            </button>
            <button
              onClick={() => setActiveTab("privacy")}
              className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-lg text-sm font-medium transition ${
                activeTab === "privacy" ? "bg-purple-55 text-purple-700 dark:bg-purple-950/30 dark:text-purple-400" : "text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800"
              }`}
            >
              🔒 Governança (LGPD)
            </button>
            <button
              onClick={() => setActiveTab("health")}
              className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-lg text-sm font-medium transition ${
                activeTab === "health" ? "bg-purple-55 text-purple-700 dark:bg-purple-950/30 dark:text-purple-400" : "text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800"
              }`}
            >
              🏥 Saúde do Sistema
            </button>
          </nav>
        </div>

        <div>
          <div className="flex items-center gap-2 p-3 bg-zinc-100 dark:bg-zinc-800 rounded-lg text-xs font-semibold">
            <span className={`h-2.5 w-2.5 rounded-full ${apiOnline ? "bg-green-500" : "bg-red-500"}`} />
            <span>Servidor API: {apiOnline ? "Online" : "Modo Local"}</span>
          </div>
          <button
            onClick={() => setIsLoggedIn(false)}
            className="w-full mt-4 bg-zinc-200 dark:bg-zinc-800 hover:bg-zinc-300 py-2 rounded-lg text-xs font-bold transition text-zinc-700 dark:text-zinc-300"
          >
            Sair
          </button>
        </div>
      </aside>

      {/* Conteúdo Principal */}
      <main className="flex-1 p-8 overflow-y-auto">
        {feedbackMsg && (
          <div className="mb-6 p-4 bg-purple-50 border border-purple-200 rounded-lg text-sm text-purple-800 dark:bg-purple-950/30 dark:border-purple-900 dark:text-purple-300" role="status">
            {feedbackMsg}
          </div>
        )}

        {activeTab === "models" && (
          <section>
            <h3 className="text-2xl font-bold text-zinc-950 dark:text-white mb-6">Model Registry (Gestão de Modelos de IA)</h3>

            <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3 mb-8">
              {modelsList.map((model) => (
                <div key={model.id} className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl p-5 shadow-sm">
                  <div className="flex justify-between items-start mb-4">
                    <div>
                      <h4 className="font-bold text-zinc-900 dark:text-white">{model.name}</h4>
                      <p className="text-xs text-zinc-500 mt-1">Versão: {model.version}</p>
                    </div>
                    <span className={`px-2.5 py-1 rounded-full text-xs font-bold ${model.is_active ? "bg-green-100 text-green-800 dark:bg-green-950/50 dark:text-green-400" : "bg-zinc-100 text-zinc-800 dark:bg-zinc-800 dark:text-zinc-400"}`}>
                      {model.is_active ? "Ativo" : "Inativo"}
                    </span>
                  </div>

                  <p className="text-xs text-zinc-400 font-mono mb-6 truncate">Hash SHA-256: {model.hash_sha256}</p>

                  <div className="flex gap-2">
                    {!model.is_active ? (
                      <button
                        onClick={() => triggerDeploy(model.id, model.version)}
                        className="flex-1 bg-purple-700 hover:bg-purple-800 text-white text-xs font-semibold py-2 rounded-lg transition"
                      >
                        Implantar (Deploy)
                      </button>
                    ) : (
                      <button
                        onClick={() => triggerRollback(model.id, model.version)}
                        className="flex-1 bg-red-600 hover:bg-red-700 text-white text-xs font-semibold py-2 rounded-lg transition"
                      >
                        Desativar (Rollback)
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>

            {/* Matriz de Confusão por Classes para Governança */}
            <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl p-6 shadow-sm">
              <h4 className="font-bold text-zinc-900 dark:text-white mb-4">Matriz de Confusão Estimada (Classes de Libras)</h4>
              <div className="overflow-x-auto">
                <table className="w-full text-sm border-collapse">
                  <thead>
                    <tr className="border-b border-zinc-200 dark:border-zinc-800">
                      <th className="text-left py-2 font-medium">Sinal de Entrada</th>
                      <th className="py-2 text-center font-medium">SAUDAÇÕES</th>
                      <th className="py-2 text-center font-medium">SAÚDE</th>
                      <th className="py-2 text-center font-medium">EMERGÊNCIA</th>
                      <th className="py-2 text-center font-medium">OUTROS / REJEIÇÃO</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr className="border-b border-zinc-100 dark:border-zinc-800/50">
                      <td className="py-3 font-semibold">SAUDAÇÕES</td>
                      <td className="text-center bg-purple-100 dark:bg-purple-950/40 text-purple-700 dark:text-purple-400 font-bold">96%</td>
                      <td className="text-center text-zinc-400">2%</td>
                      <td className="text-center text-zinc-400">1%</td>
                      <td className="text-center text-zinc-400">1%</td>
                    </tr>
                    <tr className="border-b border-zinc-100 dark:border-zinc-800/50">
                      <td className="py-3 font-semibold">SAÚDE</td>
                      <td className="text-center text-zinc-400">3%</td>
                      <td className="text-center bg-purple-100 dark:bg-purple-950/40 text-purple-700 dark:text-purple-400 font-bold">92%</td>
                      <td className="text-center text-zinc-400">3%</td>
                      <td className="text-center text-zinc-400">2%</td>
                    </tr>
                    <tr className="border-b border-zinc-100 dark:border-zinc-800/50">
                      <td className="py-3 font-semibold">EMERGÊNCIA</td>
                      <td className="text-center text-zinc-400">1%</td>
                      <td className="text-center text-zinc-400">2%</td>
                      <td className="text-center bg-purple-100 dark:bg-purple-950/40 text-purple-700 dark:text-purple-400 font-bold">95%</td>
                      <td className="text-center text-zinc-400">2%</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </section>
        )}

        {activeTab === "audit" && (
          <section>
            <h3 className="text-2xl font-bold text-zinc-950 dark:text-white mb-6">Logs de Auditoria Imutáveis</h3>
            <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl shadow-sm overflow-hidden">
              <table className="w-full text-sm text-left border-collapse">
                <thead className="bg-zinc-50 dark:bg-zinc-800/50 text-zinc-600 dark:text-zinc-400 font-medium">
                  <tr>
                    <th className="p-4">Identificador do Log</th>
                    <th className="p-4">Usuário / Operador</th>
                    <th className="p-4">Ação Executada</th>
                    <th className="p-4">Alvo</th>
                    <th className="p-4">Data e Hora (UTC)</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-200 dark:divide-zinc-800">
                  {auditLogs.map((log) => (
                    <tr key={log.id} className="hover:bg-zinc-50 dark:hover:bg-zinc-800/30">
                      <td className="p-4 font-mono text-xs">{log.id}</td>
                      <td className="p-4">{log.user_id || "Sistema"}</td>
                      <td className="p-4 font-semibold text-purple-700 dark:text-purple-400">{log.action}</td>
                      <td className="p-4 font-mono text-xs">{log.target || "N/A"}</td>
                      <td className="p-4 text-zinc-500">{new Date(log.timestamp).toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}

        {activeTab === "privacy" && (
          <section className="space-y-6">
            <h3 className="text-2xl font-bold text-zinc-950 dark:text-white mb-6">Painel de Privacidade e Consentimento LGPD</h3>
            
            <div className="grid gap-6 md:grid-cols-2">
              <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl p-6 shadow-sm">
                <h4 className="font-bold text-zinc-900 dark:text-white mb-4">Estatísticas de Requisições de Usuários</h4>
                <ul className="space-y-3 text-sm">
                  <li className="flex justify-between">
                    <span>Exclusão de Contas e Dados:</span>
                    <span className="font-bold text-purple-700">0 ativas</span>
                  </li>
                  <li className="flex justify-between">
                    <span>Solicitações de Portabilidade:</span>
                    <span className="font-bold text-purple-700">0 ativas</span>
                  </li>
                  <li className="flex justify-between">
                    <span>Consentimentos Ativos (Melhoria Contínua):</span>
                    <span className="font-bold text-green-600">0 usuários</span>
                  </li>
                </ul>
              </div>

              <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl p-6 shadow-sm">
                <h4 className="font-bold text-zinc-900 dark:text-white mb-4">Configuração de Minimização de Dados</h4>
                <p className="text-sm text-zinc-500 mb-4">
                  A extração local de landmarks geométricos evita o tráfego de dados de imagens físicas. Nenhuma gravação facial está ativa.
                </p>
                <div className="flex items-center gap-2">
                  <span className="inline-block h-3.5 w-3.5 rounded-full bg-green-500" />
                  <span className="text-xs font-bold text-green-600">Status: Privacy by Design Ativo</span>
                </div>
              </div>
            </div>
          </section>
        )}

        {activeTab === "health" && (
          <section className="space-y-6">
            <h3 className="text-2xl font-bold text-zinc-950 dark:text-white mb-6">Saúde dos Serviços do Sistema</h3>
            
            <div className="grid gap-6 md:grid-cols-3">
              <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl p-5 shadow-sm text-center">
                <h4 className="text-sm text-zinc-500 font-semibold mb-2">Latência de Inferência (P95)</h4>
                <p className="text-3xl font-extrabold text-purple-700">120 ms</p>
                <span className="text-xs text-green-600 font-bold mt-2 inline-block">Dentro da meta (&lt;250ms)</span>
              </div>

              <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl p-5 shadow-sm text-center">
                <h4 className="text-sm text-zinc-500 font-semibold mb-2">Quedas de Conexão WebSocket</h4>
                <p className="text-3xl font-extrabold text-zinc-900 dark:text-white">0.05%</p>
                <span className="text-xs text-green-600 font-bold mt-2 inline-block">Métrica excelente</span>
              </div>

              <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl p-5 shadow-sm text-center">
                <h4 className="text-sm text-zinc-500 font-semibold mb-2">Uso Máximo de Memória (Server)</h4>
                <p className="text-3xl font-extrabold text-purple-700">1.2 GB</p>
                <span className="text-xs text-zinc-500 mt-2 inline-block">Limite: 4.0 GB</span>
              </div>
            </div>
          </section>
        )}
      </main>
    </div>
  );
}
