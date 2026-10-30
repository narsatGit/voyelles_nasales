#!/usr/bin/env python3
"""
Compare l'annotation manuelle aux valeurs automatiques (WebMAUS + Praat).

Entrées (par défaut <dépôt>/donnees) :
  echantillon_a_annoter.xlsx   annotation manuelle
  cle_auto.xlsx                valeurs automatiques correspondantes (tirage_echantillon.py)

Sorties (par défaut <dépôt>/resultats) :
  par_locutrice.csv / .xlsx, par_voyelle.csv / .xlsx, detail.csv, comparaison.png, par_voyelle.png

Indicateurs
  Alignement : le milieu de la voyelle manuelle tombe dans l'intervalle WebMAUS. Les écarts de
               bornes et de formants ne portent que sur ces voyelles.
  Bornes     : écart absolu (ms) entre les bornes WebMAUS et manuelles.
  Formants   : écart (Hz) entre f1Moy / f2Moy automatiques et F1 / F2 manuels, tous moyennés sur
               la voyelle entière (Praat : « mean F1 in SELECTION »).
  Nature     : jugement manuel (N, ON, O, ?) des voyelles étiquetées nasales par l'aligneur.
  Problèmes signalés : mots « alignement » ou « transcription » dans les commentaires.

Les saisies manuelles incohérentes (fin avant début, durée > 1 s) sont signalées et leurs bornes ignorées.

Usage :
    python scripts/comparer_manuel_auto.py
    python scripts/comparer_manuel_auto.py --dossier chemin/vers/donnees --sortie chemin/vers/resultats
    python scripts/comparer_manuel_auto.py --reference francophone
"""

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# --- Seuils et réglages -------------------------------------------------------
SEUIL_BORNE_MS = 20          # borne « correcte » : écart <= 20 ms
SEUIL_F1_HZ = 100            # F1 « correct » : écart <= 100 Hz
SEUIL_F2_HZ = 200            # F2 « correct » : écart <= 200 Hz
DUREE_MANUELLE_MAX_S = 1.0   # durée manuelle maximale plausible d'une voyelle
EFFECTIF_MIN = 5             # en dessous, les pourcentages par voyelle ne sont pas interprétables
REFERENCE_DEFAUT = "francophone"   # locutrice native ; les autres sont « non natives »

NATURES = ["N", "ON", "O", "?"]
API = {"a~": "[ɑ̃]", "o~": "[ɔ̃]", "e~": "[ɛ̃]", "9~": "[œ̃]"}

# Mots-clés repérés dans les commentaires (tolèrent les fautes de frappe)
MOTIFS_ALIGNEMENT = r"al+ig"              # alignement, allignement...
MOTIFS_TRANSCRIPTION = r"tran?s?cr"       # transcription, trascription...


# --- Chargement --------------------------------------------------------------

def en_nombre(serie: pd.Series) -> pd.Series:
    """Convertit en nombres, en acceptant la virgule décimale d'Excel en français."""
    return pd.to_numeric(serie.astype(str).str.replace(",", ".", regex=False).str.strip(),
                         errors="coerce")


def charger(dossier: Path, reference: str) -> pd.DataFrame:
    ann = pd.read_excel(dossier / "echantillon_a_annoter.xlsx")
    cle = pd.read_excel(dossier / "cle_auto.xlsx")

    for c in ("deb_manuel", "fin_manuel", "f1_manuel", "f2_manuel"):
        ann[c] = en_nombre(ann[c])
    ann["nature"] = (ann["nature"].astype(str).str.strip().str.upper()
                     .replace({"NAN": np.nan, "": np.nan}))
    ann["commentaire"] = ann["commentaire"].fillna("").astype(str)

    df = ann.merge(cle.drop(columns=["locuteur", "labMot"]), on="id", how="inner")
    if len(df) < len(ann):
        print(f"[attention] {len(ann) - len(df)} ligne(s) de la feuille sans correspondance dans cle_auto.xlsx")

    df["groupe"] = np.where(df["locuteur"] == reference, "native", "non native")
    df["voyelle"] = df["labPhone"].map(API).fillna(df["labPhone"])

    # Saisies incohérentes : bornes manuelles ignorées
    duree_man = df["fin_manuel"] - df["deb_manuel"]
    df["saisie_suspecte"] = (duree_man <= 0) | (duree_man > DUREE_MANUELLE_MAX_S)
    for r in df[df["saisie_suspecte"]].itertuples():
        print(f"[saisie à vérifier] {r.id} ({r.labMot}) : début {r.deb_manuel}, fin {r.fin_manuel} "
              "-> bornes ignorées")
    df.loc[df["saisie_suspecte"], ["deb_manuel", "fin_manuel"]] = np.nan

    # Écarts (automatique - manuel)
    df["err_deb_ms"] = (df["debPhone"] - df["deb_manuel"]) * 1000
    df["err_fin_ms"] = (df["finPhone"] - df["fin_manuel"]) * 1000
    df["err_f1"] = df["f1Moy"] - df["f1_manuel"]
    df["err_f2"] = df["f2Moy"] - df["f2_manuel"]

    # Alignement : le milieu de la voyelle manuelle tombe-t-il dans l'intervalle WebMAUS ?
    milieu = (df["deb_manuel"] + df["fin_manuel"]) / 2
    ok = ((df["debPhone"] <= milieu) & (milieu <= df["finPhone"])).astype(float)
    df["aligne"] = ok.where(milieu.notna())          # 1 oui, 0 non, NaN non évaluable

    # Problèmes signalés dans les commentaires
    com = df["commentaire"].str.lower()
    df["pb_alignement"] = com.str.contains(MOTIFS_ALIGNEMENT, regex=True)
    df["pb_transcription"] = com.str.contains(MOTIFS_TRANSCRIPTION, regex=True)
    df["pb_signale"] = df["pb_alignement"] | df["pb_transcription"]
    return df


# --- Calculs -----------------------------------------------------------------

def pct(x, total) -> float:
    return round(100 * x / total, 1) if total else np.nan


def ind_nature(g: pd.DataFrame) -> dict:
    n = len(g)
    nat = g["nature"].value_counts()
    n_n, n_on, n_o, n_q = (int(nat.get(k, 0)) for k in NATURES)
    return {
        "n": n, "N": n_n, "ON": n_on, "O": n_o, "?": n_q,
        "%_N": pct(n_n, n),
        "%_non_nasale_parmi_jugees": pct(n_on + n_o, n_n + n_on + n_o),
        "%_non_confirmee (ON+O+?)": pct(n_on + n_o + n_q, n),
    }


def ind_alignement(g: pd.DataFrame) -> dict:
    evaluables = int(g["aligne"].notna().sum())
    alignes = int((g["aligne"] == 1).sum())
    return {
        "n_evaluables": evaluables, "n_alignes": alignes,
        "%_alignes_sur_la_voyelle": pct(alignes, evaluables),
        "n_pb_alignement_commentaire": int(g["pb_alignement"].sum()),
        "n_pb_transcription_commentaire": int(g["pb_transcription"].sum()),
    }


def ind_erreurs(g: pd.DataFrame) -> dict:
    """Écarts de bornes et de formants (à appeler sur les voyelles bien alignées)."""
    b = g.dropna(subset=["deb_manuel", "fin_manuel"])
    ecarts = pd.concat([b["err_deb_ms"].abs(), b["err_fin_ms"].abs()])
    deux_ok = (b["err_deb_ms"].abs() <= SEUIL_BORNE_MS) & (b["err_fin_ms"].abs() <= SEUIL_BORNE_MS)
    f = g.dropna(subset=["f1_manuel", "f2_manuel", "f1Moy", "f2Moy"])
    return {
        "n_bornes": len(b),
        "ecart_borne_median_ms": round(ecarts.median(), 1) if len(ecarts) else np.nan,
        f"%_bornes_a_{SEUIL_BORNE_MS}ms": pct(int(deux_ok.sum()), len(b)),
        "n_formants": len(f),
        "MAE_F1_Hz": round(f["err_f1"].abs().mean(), 1) if len(f) else np.nan,
        "MAE_F2_Hz": round(f["err_f2"].abs().mean(), 1) if len(f) else np.nan,
        f"%_F1_a_{SEUIL_F1_HZ}Hz": pct(int((f["err_f1"].abs() <= SEUIL_F1_HZ).sum()), len(f)),
        f"%_F2_a_{SEUIL_F2_HZ}Hz": pct(int((f["err_f2"].abs() <= SEUIL_F2_HZ).sum()), len(f)),
    }


def ligne(g: pd.DataFrame) -> dict:
    alignees = g[g["aligne"] == 1]
    err = {k + "_(alignees)": v for k, v in ind_erreurs(alignees).items()}
    return {**ind_nature(g), **ind_alignement(g), **err}


def groupes_locutrices(df: pd.DataFrame):
    for loc, g in df.groupby("locuteur"):
        yield loc, g
    non_nat = df[df["groupe"] == "non native"]
    if len(non_nat):
        yield "TOUTES_NON_NATIVES", non_nat


def table_locutrice(df: pd.DataFrame) -> pd.DataFrame:
    lignes = []
    for nom, g in groupes_locutrices(df):
        grp = "native" if (g["groupe"] == "native").all() else "non native"
        lignes.append({"locuteur": nom, "groupe": grp, **ligne(g)})
    return pd.DataFrame(lignes)


def table_voyelle(df: pd.DataFrame) -> pd.DataFrame:
    lignes = []
    for nom, g_loc in groupes_locutrices(df):
        grp = "native" if (g_loc["groupe"] == "native").all() else "non native"
        for v in API.values():
            g = g_loc[g_loc["voyelle"] == v]
            if g.empty:
                continue
            alerte = f"n<{EFFECTIF_MIN} : ne pas interpréter les %" if len(g) < EFFECTIF_MIN else ""
            lignes.append({"locuteur": nom, "groupe": grp, "voyelle": v, **ligne(g), "alerte_effectif": alerte})
    return pd.DataFrame(lignes)


# --- Figures -----------------------------------------------------------------

def figure_comparaison(df: pd.DataFrame, sortie: Path) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))
    locs = sorted(df["locuteur"].unique())
    coul = dict(zip(locs, plt.cm.tab10.colors))

    for ax, (m, a, nom) in zip(axes[0], [("f1_manuel", "f1Moy", "F1"), ("f2_manuel", "f2Moy", "F2")]):
        for loc in locs:
            g = df[df["locuteur"] == loc].dropna(subset=[m, a])
            ok, ko = g[g["aligne"] == 1], g[g["aligne"] != 1]
            ax.scatter(ok[m], ok[a], s=55, color=coul[loc], alpha=0.85, label=f"{loc} (alignée)")
            ax.scatter(ko[m], ko[a], s=60, color=coul[loc], marker="x", alpha=0.9)
        d = df[[m, a]].dropna()
        if len(d):
            lim = [d.min().min(), d.max().max()]
            ax.plot(lim, lim, "k--", lw=1)
        ax.set_xlabel(f"{nom} manuel (moyenne sur la voyelle, Hz)")
        ax.set_ylabel(f"{nom} automatique (moyenne sur la voyelle, Hz)")
        ax.set_title(f"{nom} : automatique vs manuel\n(rond = bien alignée, croix = mal alignée)")
        ax.grid(True, linestyle=":", alpha=0.5)
    axes[0][0].legend(fontsize=7)

    ax = axes[1][0]
    donnees, etiquettes = [], []
    al = df[df["aligne"] == 1]
    for loc in locs:
        g = al[al["locuteur"] == loc]
        donnees += [g["err_deb_ms"].dropna().abs(), g["err_fin_ms"].dropna().abs()]
        etiquettes += [f"{loc[:10]}\ndébut", f"{loc[:10]}\nfin"]
    if any(len(d) for d in donnees):
        ax.boxplot([d if len(d) else pd.Series([np.nan]) for d in donnees])
        ax.set_xticklabels(etiquettes)
    ax.axhline(SEUIL_BORNE_MS, color="r", ls="--", lw=1, label=f"seuil {SEUIL_BORNE_MS} ms")
    ax.set_ylabel("|écart WebMAUS - manuel| (ms)")
    ax.set_title("Écart sur les bornes (voyelles bien alignées seulement)")
    ax.legend(); ax.grid(True, axis="y", linestyle=":", alpha=0.5)

    ax = axes[1][1]
    nat = pd.crosstab(df["locuteur"], df["nature"]).reindex(columns=NATURES, fill_value=0)
    bas = np.zeros(len(nat))
    for cat, c in zip(NATURES, ["#2ca02c", "#ff7f0e", "#d62728", "#7f7f7f"]):
        part = 100 * nat[cat].values / nat.sum(axis=1).values
        ax.bar(nat.index.str[:12], part, bottom=bas, color=c, label=cat)
        bas += part
    ax.set_ylabel("% des voyelles étiquetées nasales par l'aligneur")
    ax.set_title("Jugement manuel : N nasale, ON orale + nasale, O orale")
    ax.legend()
    fig.tight_layout(); fig.savefig(sortie, dpi=200); plt.close(fig)


def figure_voyelle(df: pd.DataFrame, sortie: Path) -> None:
    """Par timbre : % non confirmées nasales (ligne du haut) et % alignées (ligne du bas)."""
    non_nat = sorted(df[df["groupe"] == "non native"]["locuteur"].unique())
    jeux = [(loc, df[df["locuteur"] == loc]) for loc in non_nat]
    if len(non_nat) > 1:
        jeux.append(("Ensemble des non natives", df[df["groupe"] == "non native"]))
    if not jeux:
        return
    ordre = list(API.values())
    fig, axes = plt.subplots(2, len(jeux), figsize=(5 * len(jeux), 9), sharey=True, squeeze=False)
    for j, (titre, g) in enumerate(jeux):
        n = np.array([(g["voyelle"] == v).sum() for v in ordre])
        ax = axes[0][j]
        bas = np.zeros(len(ordre))
        for cat, c in zip(["ON", "O", "?"], ["#ff7f0e", "#d62728", "#7f7f7f"]):
            val = np.array([100 * ((g["voyelle"] == v) & (g["nature"] == cat)).sum() / max(1, (g["voyelle"] == v).sum())
                            for v in ordre])
            ax.bar(ordre, val, bottom=bas, color=c, label=cat)
            bas += val
        for x, (tot, eff) in enumerate(zip(bas, n)):
            ax.text(x, tot + 1.5, f"n={eff}", ha="center", fontsize=9)
        ax.set_title(titre); ax.set_ylim(0, 112); ax.grid(True, axis="y", linestyle=":", alpha=0.5)

        ax = axes[1][j]
        val, txt = [], []
        for v in ordre:
            s = g[(g["voyelle"] == v) & g["aligne"].notna()]
            val.append(100 * (s["aligne"] == 1).sum() / len(s) if len(s) else 0)
            txt.append(f"{int((s['aligne'] == 1).sum())}/{len(s)}")
        ax.bar(ordre, val, color="#1f77b4")
        for x, (h, t) in enumerate(zip(val, txt)):
            ax.text(x, h + 1.5, t, ha="center", fontsize=9)
        ax.set_ylim(0, 112); ax.grid(True, axis="y", linestyle=":", alpha=0.5)
    axes[0][0].set_ylabel("% non confirmées nasales (ON, O, ?)")
    axes[1][0].set_ylabel("% bien alignées sur la voyelle")
    axes[0][-1].legend(title="jugement")
    fig.suptitle("Par timbre de voyelle nasale : jugement manuel (haut) et alignement WebMAUS (bas)", fontsize=12)
    fig.tight_layout(); fig.savefig(sortie, dpi=200); plt.close(fig)


# --- Programme principal -----------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Comparaison annotations manuelles / valeurs automatiques.")
    parser.add_argument("--dossier", default=None, help="dossier des données (défaut : <dépôt>/donnees)")
    parser.add_argument("--sortie", default=None, help="dossier des résultats (défaut : <dépôt>/resultats)")
    parser.add_argument("--reference", default=REFERENCE_DEFAUT,
                        help=f"nom de la locutrice native, tel qu'écrit dans la colonne locuteur (défaut : {REFERENCE_DEFAUT})")
    args = parser.parse_args()
    racine = Path(__file__).resolve().parent.parent
    dossier = Path(args.dossier) if args.dossier else racine / "donnees"
    sortie = Path(args.sortie) if args.sortie else racine / "resultats"
    sortie.mkdir(parents=True, exist_ok=True)

    df = charger(dossier, args.reference)
    if (df["locuteur"] == args.reference).sum() == 0:
        print(f"[attention] aucune ligne pour la référence '{args.reference}' : "
              f"locutrices présentes = {sorted(df['locuteur'].unique())}. Utilisez --reference.")
    remplies = int(df[["deb_manuel", "fin_manuel", "f1_manuel", "f2_manuel", "nature"]].notna().any(axis=1).sum())
    print(f"{len(df)} voyelles dans l'échantillon, {remplies} annotées.")
    if remplies == 0:
        print("La feuille d'annotation est vide : rien à comparer.")
        return

    loc, voy = table_locutrice(df), table_voyelle(df)
    pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40)
    print("\n=== COMPARAISON DES LOCUTRICES ===")
    print(loc.to_string(index=False))
    print("\n=== PAR TIMBRE DE VOYELLE ===")
    print(voy.to_string(index=False))

    loc.to_csv(sortie / "par_locutrice.csv", index=False)
    voy.to_csv(sortie / "par_voyelle.csv", index=False)
    df.to_csv(sortie / "detail.csv", index=False)
    loc.to_excel(sortie / "par_locutrice.xlsx", index=False)
    voy.to_excel(sortie / "par_voyelle.xlsx", index=False)
    figure_comparaison(df, sortie / "comparaison.png")
    figure_voyelle(df, sortie / "par_voyelle.png")
    print(f"\n-> {sortie}/ : par_locutrice, par_voyelle (csv + xlsx), detail.csv, comparaison.png, par_voyelle.png")


if __name__ == "__main__":
    main()
