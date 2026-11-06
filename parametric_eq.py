"""
Pricing d'une couverture paramétrique tremblement de terre (index = PGA) — Python pur.

Chaîne complète :
  1. Modèle d'aléa      : fréquence Poisson + magnitudes Gutenberg-Richter tronquée + localisation
  2. Index              : PGA au site via une GMPE simplifiée (lognormale)
  3. Payout paramétrique: fonction en escalier sur le PGA
  4. Pricing            : AAL, écart-type, VaR/TVaR, prime (principe écart-type et coût du capital)
  5. Incertitude        : paramètres estimés (bootstrap paramétrique) -> distribution de la prime
  6. Basis risk         : payout vs perte réelle (fonction de vulnérabilité + bruit)
  7. Design du trigger  : arbitrage prime / basis risk
  8. Sensibilités

ATTENTION : les paramètres de l'aléa (taux, b-value, GMPE) sont STYLISÉS et le catalogue est
simulé. Ce n'est pas un modèle calibré sur une région réelle. Pour une vraie étude, remplacer
`simulate_events` par un catalogue historique (USGS, ISC-GEM) et la GMPE par une GMPE publiée
(ex. NGA-West2) : le reste de la chaîne ne change pas.
"""
from dataclasses import dataclass, replace
import numpy as np
import pandas as pd

RNG_SEED = 2026


# --------------------------------------------------------------------------- 1. Aléa
@dataclass(frozen=True)
class Hazard:
    rate: float = 3.0          # événements M >= m_min par an dans la zone
    b: float = 1.0             # b-value de Gutenberg-Richter
    m_min: float = 5.0
    m_max: float = 8.0
    radius_km: float = 150.0   # zone source : disque autour du site
    depth_km: float = 10.0


@dataclass(frozen=True)
class GMPE:
    """ln(PGA[g]) = c0 + c1 (M-6) - c2 ln(sqrt(R^2+h^2)/10) + eps, eps ~ N(0, sigma^2)"""
    c0: float = -1.9
    c1: float = 1.0
    c2: float = 1.2
    sigma: float = 0.6


def sample_magnitudes(n, h: Hazard, rng):
    """Inversion de la loi de Gutenberg-Richter tronquée [m_min, m_max]."""
    beta = h.b * np.log(10)
    u = rng.random(n)
    c = 1 - np.exp(-beta * (h.m_max - h.m_min))
    return h.m_min - np.log(1 - u * c) / beta


def simulate_events(h: Hazard, g: GMPE, n_years: int, rng):
    """Retourne un DataFrame (year, mag, dist_km, pga_g) pour n_years années simulées."""
    counts = rng.poisson(h.rate, n_years)
    n = counts.sum()
    year = np.repeat(np.arange(n_years), counts)
    mag = sample_magnitudes(n, h, rng)
    dist = h.radius_km * np.sqrt(rng.random(n))        # uniforme dans le disque
    r = np.sqrt(dist**2 + h.depth_km**2)
    ln_pga = g.c0 + g.c1 * (mag - 6) - g.c2 * np.log(r / 10) + g.sigma * rng.standard_normal(n)
    return pd.DataFrame({"year": year, "mag": mag, "dist_km": dist, "pga_g": np.exp(ln_pga)})


# --------------------------------------------------------------------------- 2-3. Index & payout
@dataclass(frozen=True)
class Cover:
    limit: float = 10_000_000.0
    thresholds: tuple = (0.08, 0.15, 0.25)   # PGA en g
    payout_pct: tuple = (0.25, 0.50, 1.00)   # part de la limite


def payout(pga, c: Cover):
    pga = np.asarray(pga)
    out = np.zeros_like(pga, dtype=float)
    for t, p in zip(c.thresholds, c.payout_pct):
        out = np.where(pga >= t, p, out)
    return out * c.limit


def annual_payouts(events: pd.DataFrame, c: Cover, n_years: int):
    """Payout annuel : somme des payouts par événement, plafonnée à la limite (aggregate limit)."""
    ev_pay = payout(events["pga_g"].values, c)
    ann = np.bincount(events["year"].values, weights=ev_pay, minlength=n_years)
    return np.minimum(ann, c.limit)


# --------------------------------------------------------------------------- 4. Pricing
def risk_metrics(ann, limit, sd_load=0.35, coc=0.10, conf=0.99):
    aal = ann.mean()
    sd = ann.std(ddof=1)
    var = np.quantile(ann, conf)
    # For a discrete payout distribution, including every observation tied at VaR
    # overweights the tail. Use the largest (1-conf) fraction of observations.
    tail_n = max(1, int(np.ceil((1 - conf) * len(ann))))
    tail = np.partition(ann, len(ann) - tail_n)[-tail_n:]
    tvar = tail.mean() if len(tail) else var
    return {
        "AAL": aal,
        "Std": sd,
        f"VaR{int(conf*100)}": var,
        f"TVaR{int(conf*100)}": tvar,
        "prob_trigger": (ann > 0).mean(),
        "premium_sd": aal + sd_load * sd,                 # principe de l'écart-type
        "premium_coc": aal + coc * max(tvar - aal, 0),    # coût du capital sur (TVaR - AAL)
        "ROL_sd": (aal + sd_load * sd) / limit,           # rate on line
    }


def ep_curve(ann, rps=(5, 10, 25, 50, 100, 250, 500)):
    """Perte pour chaque période de retour (courbe OEP/AEP sur pertes annuelles)."""
    return pd.Series({rp: np.quantile(ann, 1 - 1 / rp) for rp in rps}, name="loss")


# --------------------------------------------------------------------------- 5. Incertitude
def parameter_uncertainty(h_true: Hazard, g: GMPE, c: Cover, obs_years=60, n_boot=200,
                          sim_years=20_000, seed=RNG_SEED):
    """
    On suppose qu'on observe `obs_years` ans de catalogue. On ré-estime (rate, b) par MLE sur
    des catalogues pseudo-observés, puis on reprice. La dispersion de la prime = risque de modèle.
    """
    rng = np.random.default_rng(seed)
    prem = []
    for _ in range(n_boot):
        n_obs = rng.poisson(h_true.rate * obs_years)
        n_obs = max(n_obs, 5)
        m = sample_magnitudes(n_obs, h_true, rng)
        rate_hat = n_obs / obs_years
        # MLE d'Aki pour b : b = 1 / (ln10 * (mean(m) - m_min))
        b_hat = 1 / (np.log(10) * (m.mean() - h_true.m_min))
        h_hat = replace(h_true, rate=rate_hat, b=b_hat)
        ev = simulate_events(h_hat, g, sim_years, rng)
        ann = annual_payouts(ev, c, sim_years)
        prem.append(risk_metrics(ann, c.limit)["premium_sd"])
    return np.array(prem)


# --------------------------------------------------------------------------- 6. Basis risk
def true_damage_ratio(pga, rng, noise=0.5):
    """
    Perte réelle (part de la limite) : vulnérabilité lognormale-sigmoïde du PGA *réel* au portefeuille,
    avec bruit multiplicatif. L'index mesuré (PGA au site de référence) diffère du PGA réel
    -> écart = basis risk. Loi : DR = Phi((ln pga - ln 0.35)/0.7), x bruit lognormal, plafonné à 1.
    """
    from scipy.stats import norm
    dr = norm.cdf((np.log(pga) - np.log(0.35)) / 0.7)
    dr = dr * np.exp(noise * rng.standard_normal(len(pga)) - noise**2 / 2)
    return np.clip(dr, 0, 1)


def simulate_basis(h: Hazard, g: GMPE, c: Cover, n_years=50_000, spatial_sigma=0.4, seed=RNG_SEED):
    """
    Pour chaque événement : PGA à la station de référence (index) et PGA réel au portefeuille
    = index x erreur spatiale lognormale (sigma = spatial_sigma). Perte réelle annuelle vs payout.
    """
    rng = np.random.default_rng(seed)
    ev = simulate_events(h, g, n_years, rng)
    pga_idx = ev["pga_g"].values
    pga_true = pga_idx * np.exp(spatial_sigma * rng.standard_normal(len(ev)) - spatial_sigma**2 / 2)
    loss_ev = true_damage_ratio(pga_true, rng) * c.limit
    ev_pay = payout(pga_idx, c)
    loss = np.minimum(np.bincount(ev["year"], weights=loss_ev, minlength=n_years), c.limit)
    pay = np.minimum(np.bincount(ev["year"], weights=ev_pay, minlength=n_years), c.limit)
    return loss, pay


def basis_metrics(loss, pay, limit, material=0.05):
    """Métriques de basis risk sur les années à perte matérielle (> material x limite)."""
    big = loss > material * limit
    return {
        "corr": float(np.corrcoef(loss, pay)[0, 1]) if pay.std() > 0 and loss.std() > 0 else float("nan"),
        "P(loss material & no payout)": (big & (pay == 0)).mean(),
        "P(payout & loss immaterial)": ((~big) & (pay > 0)).mean(),
        "mean shortfall": np.maximum(loss - pay, 0).mean(),
        "mean overpay": np.maximum(pay - loss, 0).mean(),
        "RMSE": np.sqrt(np.mean((loss - pay) ** 2)),
    }


# --------------------------------------------------------------------------- 7. Design
def trigger_frontier(h: Hazard, g: GMPE, limit, thresholds_grid, n_years=40_000, seed=RNG_SEED):
    """
    Cover binaire (payout 100% si PGA >= t). Pour chaque t : prime (sd) et basis risk (RMSE, shortfall).
    """
    rows = []
    loss_ref = None
    for t in thresholds_grid:
        c = Cover(limit=limit, thresholds=(t,), payout_pct=(1.0,))
        loss, pay = simulate_basis(h, g, c, n_years=n_years, seed=seed)
        m = basis_metrics(loss, pay, limit)
        r = risk_metrics(pay, limit)
        rows.append({"trigger_g": t, "premium": r["premium_sd"], "ROL": r["ROL_sd"],
                     "prob_trigger": r["prob_trigger"], "RMSE": m["RMSE"],
                     "P(loss&no pay)": m["P(loss material & no payout)"],
                     "P(pay&no loss)": m["P(payout & loss immaterial)"]})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- 8. Sensibilités
def sensitivity(h: Hazard, g: GMPE, c: Cover, n_years=60_000, seed=RNG_SEED):
    base_rng = np.random.default_rng(seed)
    base = risk_metrics(annual_payouts(simulate_events(h, g, n_years, base_rng), c, n_years), c.limit)["premium_sd"]
    scen = {
        "rate x0.8": (replace(h, rate=h.rate * 0.8), g),
        "rate x1.2": (replace(h, rate=h.rate * 1.2), g),
        "b = 0.9": (replace(h, b=0.9), g),
        "b = 1.1": (replace(h, b=1.1), g),
        "sigma GMPE 0.5": (h, replace(g, sigma=0.5)),
        "sigma GMPE 0.7": (h, replace(g, sigma=0.7)),
        "atténuation c2 = 1.0": (h, replace(g, c2=1.0)),
        "atténuation c2 = 1.4": (h, replace(g, c2=1.4)),
    }
    rows = []
    for name, (hh, gg) in scen.items():
        rng = np.random.default_rng(seed)
        p = risk_metrics(annual_payouts(simulate_events(hh, gg, n_years, rng), c, n_years), c.limit)["premium_sd"]
        rows.append({"scenario": name, "premium": p, "delta_vs_base_%": 100 * (p / base - 1)})
    return base, pd.DataFrame(rows)
