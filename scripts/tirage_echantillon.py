#!/usr/bin/env python3
"""
Tirage d'un échantillon de voyelles nasales à annoter manuellement.

Entrées (par défaut <dépôt>/donnees) : resultat_<nom>.txt (extraction_voyelles.praat) et <nom>.TextGrid.
Tire au hasard N voyelles nasales par locutrice (tirage reproductible, au moins 2 par timbre si possible).

Sorties :
  echantillon_a_annoter.xlsx   feuille à remplir ; elle ne contient aucune valeur automatique,
                               seulement les bornes du mot qui contient la voyelle
  cle_auto.xlsx                valeurs automatiques correspondantes, à consulter après l'annotation

Colonnes à remplir (voir docs/protocole_annotation.md) :
  deb_manuel, fin_manuel   début et fin de la voyelle (s)
  f1_manuel, f2_manuel     F1 et F2 moyennés sur la voyelle sélectionnée (Hz)
  nature                   N, ON, O ou ?
  commentaire              libre

Une nouvelle exécution réécrit les deux fichiers.

Usage :
    python scripts/tirage_echantillon.py
    python scripts/tirage_echantillon.py --n 20 --graine 42 --dossier chemin/vers/donnees
"""

import argparse
import re
from pathlib import Path

import numpy as np
import pandas as pd


def lire_resultat(chemin: Path) -> pd.DataFrame:
    brut = chemin.read_bytes()
    enc = "utf-16" if brut[:2] in (b"\xff\xfe", b"\xfe\xff") else "utf-8-sig"
    return pd.read_csv(chemin, sep="\t", encoding=enc, na_values=["NA"])


def lire_mots(chemin: Path) -> list[tuple[float, float, str]]:
    """Intervalles non vides du tier ORT-MAU (mots)."""
    brut = chemin.read_bytes()
    for enc in ("utf-8-sig", "utf-16"):
        try:
            texte = brut.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    for bloc in re.split(r"\n\s*item \[\d+\]:", texte)[1:]:
        if 'name = "ORT-MAU"' in bloc:
            ivs = re.findall(r'xmin = ([\d.eE+-]+)\s*\n\s*xmax = ([\d.eE+-]+)\s*\n\s*text = "(.*?)"',
                             bloc, flags=re.S)
            return [(float(a), float(b), t) for a, b, t in ivs if t.strip()]
    raise ValueError("tier ORT-MAU introuvable")


def tirer(df: pd.DataFrame, n: int, graine: int, min_par_timbre: int = 2) -> pd.DataFrame:
    """Tirage aléatoire : au moins `min_par_timbre` par voyelle nasale, puis complété au hasard."""
    rng = np.random.default_rng(graine)
    choisis = []
    for _, g in df.groupby("labPhone"):
        k = min(min_par_timbre, len(g))
        choisis += list(rng.choice(g.index, size=k, replace=False))
    reste = df.index.difference(choisis)
    k = min(max(0, n - len(choisis)), len(reste))
    choisis += list(rng.choice(reste, size=k, replace=False))
    return df.loc[rng.permutation(choisis)]


def main() -> None:
    parser = argparse.ArgumentParser(description="Tirage de l'échantillon à annoter manuellement.")
    parser.add_argument("--dossier", default=None, help="dossier des données (défaut : <dépôt>/donnees)")
    parser.add_argument("--n", type=int, default=15, help="voyelles nasales tirées par locutrice (défaut : 15)")
    parser.add_argument("--graine", type=int, default=42, help="graine du tirage (défaut : 42)")
    args = parser.parse_args()

    dossier = Path(args.dossier) if args.dossier else Path(__file__).resolve().parent.parent / "donnees"
    fichiers = sorted(dossier.glob("resultat_*.txt"))
    if not fichiers:
        print(f"Aucun fichier resultat_*.txt dans : {dossier}")
        return

    a_annoter, cle = [], []
    for f in fichiers:
        nom = f.stem[len("resultat_"):]
        df = lire_resultat(f)
        nasales = df[df["type"] == "nasale"].copy()
        if nasales.empty:
            print(f"[ignoré] {f.name} : aucune voyelle nasale")
            continue

        tg = dossier / f"{nom}.TextGrid"
        mots = lire_mots(tg) if tg.exists() else []
        if not mots:
            print(f"[attention] {tg.name} introuvable : les bornes des mots ne seront pas indiquées")

        # Pour chaque nasale : mot qui la contient et rang parmi les nasales de ce mot
        deb_mot, fin_mot, rang = [], [], []
        for _, r in nasales.iterrows():
            milieu = (r["debPhone"] + r["finPhone"]) / 2
            m = next(((a, b) for a, b, _ in mots if a <= milieu <= b), (np.nan, np.nan))
            deb_mot.append(m[0]); fin_mot.append(m[1])
            memes = nasales[(nasales["debPhone"] >= m[0] - 1e-6) & (nasales["debPhone"] < r["debPhone"] - 1e-6)
                            & (nasales["finPhone"] <= m[1] + 1e-6)] if not np.isnan(m[0]) else []
            rang.append(len(memes) + 1)
        nasales["deb_mot"], nasales["fin_mot"], nasales["rang_dans_mot"] = deb_mot, fin_mot, rang

        tirage = tirer(nasales, args.n, args.graine).reset_index(drop=True)
        tirage["id"] = [f"{nom}_{i + 1:02d}" for i in range(len(tirage))]
        tirage["locuteur"] = nom
        print(f"{nom} : {len(tirage)} voyelles nasales tirées sur {len(nasales)} "
              f"({tirage['labPhone'].value_counts().to_dict()})")

        a_annoter.append(pd.DataFrame({
            "id": tirage["id"], "locuteur": nom, "audio": f"{nom}.wav",
            "labMot": tirage["labMot"], "deb_mot": tirage["deb_mot"].round(3),
            "fin_mot": tirage["fin_mot"].round(3), "rang_dans_mot": tirage["rang_dans_mot"],
            "deb_manuel": "", "fin_manuel": "", "f1_manuel": "", "f2_manuel": "",
            "nature": "", "commentaire": "",
        }))
        cle.append(tirage[["id", "locuteur", "labPhone", "labMot", "debPhone", "finPhone", "duree",
                           "f1", "f2", "f1Moy", "f2Moy", "exploitable", "precedent", "suivant"]])

    if not a_annoter:
        return
    pd.concat(a_annoter).to_excel(dossier / "echantillon_a_annoter.xlsx", index=False)
    pd.concat(cle).to_excel(dossier / "cle_auto.xlsx", index=False)
    print("\n-> echantillon_a_annoter.xlsx (à remplir)\n-> cle_auto.xlsx (ne pas ouvrir avant la fin)")


if __name__ == "__main__":
    main()
