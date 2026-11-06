"""Exécute l'étude complète et écrit tables + figures dans ./outputs."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import parametric_eq as pe

OUT = Path(__file__).parent / "outputs"
OUT.mkdir(exist_ok=True)

h, g, c = pe.Hazard(), pe.GMPE(), pe.Cover()
N = 200_000
rng = np.random.default_rng(pe.RNG_SEED)

# 1-4 : pricing de base -----------------------------------------------------------------------
ev = pe.simulate_events(h, g, N, rng)
ann = pe.annual_payouts(ev, c, N)
metrics = pe.risk_metrics(ann, c.limit)
ep = pe.ep_curve(ann)
print("== Pricing de base ==")
for k, v in metrics.items():
    print(f"{k:>14}: {v:,.4f}" if v < 10 else f"{k:>14}: {v:,.0f}")
print("\n== Courbe EP (perte annuelle par période de retour) ==")
print(ep.round(0).to_string())

# 5 : incertitude de paramètres ---------------------------------------------------------------
prem_boot = pe.parameter_uncertainty(h, g, c)
unc = {"mean": prem_boot.mean(), "p5": np.quantile(prem_boot, .05), "p95": np.quantile(prem_boot, .95),
       "cv": prem_boot.std() / prem_boot.mean()}
print("\n== Incertitude de paramètres (60 ans de catalogue) ==")
print({k: round(float(v), 3) if k == "cv" else round(float(v)) for k, v in unc.items()})

# 6 : basis risk ------------------------------------------------------------------------------
loss, pay = pe.simulate_basis(h, g, c, n_years=100_000)
bm = pe.basis_metrics(loss, pay, c.limit)
print("\n== Basis risk (cover escalier 3 paliers) ==")
for k, v in bm.items():
    print(f"{k:>30}: {v:,.4f}" if v < 10 else f"{k:>30}: {v:,.0f}")

# 7 : design du trigger -----------------------------------------------------------------------
frontier = pe.trigger_frontier(h, g, c.limit, np.round(np.arange(0.04, 0.321, 0.04), 2))
print("\n== Frontière trigger binaire ==")
print(frontier.round(4).to_string(index=False))

# 8 : sensibilités ----------------------------------------------------------------------------
base_prem, sens = pe.sensitivity(h, g, c)
print(f"\n== Sensibilités (prime de base = {base_prem:,.0f}) ==")
print(sens.round(1).to_string(index=False))

# Export tables
frontier.to_csv(OUT / "trigger_frontier.csv", index=False)
sens.to_csv(OUT / "sensitivity.csv", index=False)
ep.to_csv(OUT / "ep_curve.csv")
json.dump({"base": {k: float(v) for k, v in metrics.items()},
           "param_uncertainty": {k: float(v) for k, v in unc.items()},
           "basis": {k: float(v) for k, v in bm.items()}},
          open(OUT / "summary.json", "w"), indent=2)

# Figures -------------------------------------------------------------------------------------
plt.rcParams.update({"figure.dpi": 130, "axes.spines.top": False, "axes.spines.right": False})

# (a) Structure de payout + distribution PGA
fig, ax = plt.subplots(1, 2, figsize=(11, 4))
x = np.linspace(0, 0.6, 400)
ax[0].step(x, pe.payout(x, c) / 1e6, where="post", color="#1f4e79")
ax[0].set_xlabel("PGA à la station de référence (g)"); ax[0].set_ylabel("Payout (M$)")
ax[0].set_title("Structure de payout paramétrique")
ax[1].hist(np.log10(ev["pga_g"]), bins=80, color="#7a9cc6")
for t in c.thresholds:
    ax[1].axvline(np.log10(t), color="crimson", ls="--", lw=1)
ax[1].set_xlabel("log10 PGA (g)"); ax[1].set_title("Distribution du PGA par événement (triggers en rouge)")
fig.tight_layout(); fig.savefig(OUT / "fig1_payout_pga.png"); plt.close(fig)

# (b) Courbe EP
fig, ax = plt.subplots(figsize=(6, 4))
ax.semilogx(ep.index, ep.values / 1e6, "o-", color="#1f4e79")
ax.set_xlabel("Période de retour (ans)"); ax.set_ylabel("Perte annuelle (M$)")
ax.set_title("Courbe EP du payout annuel")
fig.tight_layout(); fig.savefig(OUT / "fig2_ep_curve.png"); plt.close(fig)

# (c) Incertitude de paramètres
fig, ax = plt.subplots(figsize=(6, 4))
ax.hist(prem_boot / 1e3, bins=30, color="#7a9cc6")
ax.axvline(metrics["premium_sd"] / 1e3, color="crimson", ls="--", label="prime (vrais paramètres)")
ax.set_xlabel("Prime (k$)"); ax.set_title("Risque de modèle : prime selon paramètres estimés")
ax.legend(); fig.tight_layout(); fig.savefig(OUT / "fig3_param_uncertainty.png"); plt.close(fig)

# (d) Frontière prime / basis risk
fig, ax = plt.subplots(1, 2, figsize=(11, 4))
ax[0].semilogy(frontier["trigger_g"], frontier["ROL"] * 100, "o-", color="#1f4e79", label="Rate on line (%)")
ax[0].semilogy(frontier["trigger_g"], frontier["prob_trigger"] * 100, "s--", color="#7a9cc6", label="Prob. de déclenchement (%)")
ax[0].set_xlabel("Seuil de déclenchement (g)"); ax[0].set_ylabel("%")
ax[0].set_title("Coût du cover selon le trigger"); ax[0].legend(fontsize=8)
ax[1].plot(frontier["trigger_g"], frontier["P(loss&no pay)"], "o-", label="perte matérielle sans payout")
ax[1].plot(frontier["trigger_g"], frontier["P(pay&no loss)"], "s-", label="payout sans perte matérielle")
ax[1].set_xlabel("Seuil de déclenchement (g)"); ax[1].set_ylabel("Probabilité annuelle")
ax[1].set_title("Erreurs de type I / II selon le trigger"); ax[1].legend(fontsize=8)
fig.tight_layout(); fig.savefig(OUT / "fig4_trigger_frontier.png"); plt.close(fig)

# (e) Tornado
s = sens.sort_values("delta_vs_base_%")
fig, ax = plt.subplots(figsize=(6, 4))
ax.barh(s["scenario"], s["delta_vs_base_%"], color=["#c0504d" if v < 0 else "#1f4e79" for v in s["delta_vs_base_%"]])
ax.set_xlabel("Variation de la prime (%)"); ax.set_title("Sensibilité de la prime aux hypothèses")
fig.tight_layout(); fig.savefig(OUT / "fig5_sensitivity.png"); plt.close(fig)
print("\nFigures et tables écrites dans", OUT)
