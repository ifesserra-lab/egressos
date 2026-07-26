"""Fomento FAPES da coorte de egressos.
Lê a base FAPES (relatorio_alocacao_bolsas.json do fapes-dashboard) e agrega os projetos-âncora
que financiaram os egressos. Vínculo egresso↔projeto é CURADO (verificado por projeto+período+
sigla — cross por nome puro dá homônimo). Saída: data/fapes_fomento.json.
"""
import json, re, pathlib

BASE = pathlib.Path("/caminho/para/salario")
FAPES = pathlib.Path("/caminho/para/fapes-dashboard/downloads/relatorio_alocacao_bolsas.json")

# projeto-âncora -> egressos (ids do alunos.json) verificados por projeto+período+sigla
ANCORA = {
    "34552": ["barbosa", "gary", "helen", "marialuiza", "icaro"],   # ES na Palma da Mão (BPIG)
    "39212": ["tarcisio"],                                          # Acesso Cidadão (AT-NM)
}

def br2f(s):
    s = str(s or "").strip()
    return float(s.replace(".", "").replace(",", ".")) if re.search(r"\d", s) else 0.0

def build():
    if not FAPES.exists():
        return None
    base = json.load(open(FAPES))
    projetos = []
    for pid, egr in ANCORA.items():
        rs = [r for r in base if r.get("projeto_id") == pid]
        if not rs: continue
        r0 = rs[0]
        projetos.append({
            "projeto_id": pid,
            "titulo": r0.get("projeto_titulo"),
            "situacao": r0.get("situacao_descricao"),
            "instituicao": r0.get("instituicao_sigla"),
            "bolsa_sigla": sorted({r.get("bolsa_sigla") for r in rs}),
            "bolsistas": len({r.get("bolsista_pesquisador_nome") for r in rs}),
            "valor_alocado": round(sum(br2f(r.get("valor_alocado_total")) for r in rs)),
            "periodo": [min(r.get("formulario_bolsa_inicio","") for r in rs)[:7],
                        max(r.get("formulario_bolsa_termino","") for r in rs)[:7]],
            "egressos": len(egr),
        })
    tot = {
        "valor_total": sum(p["valor_alocado"] for p in projetos),
        "bolsistas_total": sum(p["bolsistas"] for p in projetos),
        "egressos_total": sum(p["egressos"] for p in projetos),
        "n_projetos": len(projetos),
    }
    # DESFECHO (impacto): onde os egressos bolsistas FAPES estão hoje
    import statistics
    ids = [i for lst in ANCORA.values() for i in lst]
    al = json.load(open(BASE/"alunos.json"))["alunos"]
    cons = json.load(open(BASE/"data/consolidado.json"))
    order = ["barbosa","gary","possatti","helen","renan","andre","tarcisio","joel","icaro","gustavo","marialuiza",
             "gabriel_barboza","magnago","martins_miranda","geann","rodrigo_maia","andre_aguiar",
             "guilherme_gatti","ivana","joao_paulo","lucas_coutinho","marcos_dias","phillipe"]
    medatual = {order[i]: cons["perfis"][i]["med_atual"] for i in range(min(len(order), len(cons["perfis"])))}
    meds = [medatual[i] for i in ids if i in medatual]
    em_tech = sum(1 for a in al if a["id"] in ids and a["ainda_em_tech"])
    BOLSA_EPOCA, BOLSA_2026 = 800, 1187
    med_hoje = round(statistics.median(meds)) if meds else None
    desfecho = {
        "egressos": len(ids), "em_tech": em_tech,
        "mediana_hoje": med_hoje,
        "bolsa_epoca_mensal": BOLSA_EPOCA, "bolsa_em_2026": BOLSA_2026,
        "mult_nominal": round(med_hoje/BOLSA_EPOCA) if med_hoje else None,
        "mult_real": round(med_hoje/BOLSA_2026) if med_hoje else None,
    }
    return {"projetos": projetos, "total": tot, "desfecho": desfecho,
            "fonte": "FAPES · relatorio_alocacao_bolsas (via PRODEST); vínculo egresso↔projeto curado"}

if __name__ == "__main__":
    out = build()
    if not out:
        # A base da FAPES vive em outro repositório e nem sempre está montada (ex.: CI).
        # Se já houver um fapes_fomento.json gerado antes, mantém e segue — o dado é
        # histórico e não muda de mês para mês. Só falha se nunca tiver sido gerado.
        alvo = BASE / "data/fapes_fomento.json"
        if alvo.exists():
            print(f"base FAPES não encontrada ({FAPES}) — mantendo {alvo.name} existente")
            raise SystemExit(0)
        print("base FAPES não encontrada:", FAPES); raise SystemExit(1)
    json.dump(out, open(BASE/"data/fapes_fomento.json", "w"), ensure_ascii=False, indent=1)
    for p in out["projetos"]:
        print(f"  {p['projeto_id']} {p['titulo'][:40]:<40} | {p['bolsistas']} bolsistas ({','.join(p['bolsa_sigla'])}) | "
              f"R$ {p['valor_alocado']:,} | {p['periodo'][0]}→{p['periodo'][1]} | egressos={p['egressos']}")
    t = out["total"]
    print(f"TOTAL: R$ {t['valor_total']:,} | {t['bolsistas_total']} bolsistas | {t['egressos_total']} egressos | {t['n_projetos']} projetos")
    d = out["desfecho"]
    print(f"DESFECHO: {d['em_tech']}/{d['egressos']} em tech | mediana hoje R$ {d['mediana_hoje']:,} | "
          f"~{d['mult_nominal']}x nominal / ~{d['mult_real']}x real vs bolsa")
