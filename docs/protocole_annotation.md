# Protocole d'annotation manuelle

L'annotation manuelle porte sur un échantillon de voyelles nasales tirées au hasard. Elle est ensuite comparée aux valeurs automatiques (alignement WebMAUS, mesures Praat).

| Tâche | Annotation manuelle | Comparée à |
| --- | --- | --- |
| Nature | jugement auditif : la voyelle est-elle réellement nasale ? | étiquette de WebMAUS (toujours « voyelle nasale ») |
| Bornes | début et fin de la voyelle | bornes de WebMAUS |
| Formants | F1 et F2 moyennés sur la voyelle | `f1Moy` et `f2Moy` de l'extraction Praat |

## Prérequis

`resultat_<nom>.txt` (produit par `scripts/extraction_voyelles.praat`), `<nom>.wav` et `<nom>.TextGrid` dans `donnees/`, et les bibliothèques de `requirements.txt`.

## 1. Tirer l'échantillon

```bash
python scripts/tirage_echantillon.py --n 20
```

Deux fichiers sont écrits dans `donnees/` :

- `echantillon_a_annoter.xlsx` : la feuille à remplir, sans aucune valeur automatique ; elle donne seulement les bornes du mot qui contient la voyelle ;
- `cle_auto.xlsx` : les valeurs automatiques correspondantes, à ne consulter qu'après l'annotation.

Une nouvelle exécution réécrit ces deux fichiers, donc aussi la feuille annotée.

## 2. Annoter dans Praat

Chaque ligne de la feuille est **une voyelle nasale** ; le mot (`labMot`) sert à la retrouver. Pour chaque ligne :

1. Ouvrir le `.wav` seul (colonne `audio`) : *Open > Read from file…*, puis *View & Edit*. Le TextGrid reste fermé afin de ne pas voir les bornes de WebMAUS.
2. Aller au mot : *View > Zoom…* avec `deb_mot` et `fin_mot`. Si le mot contient plusieurs voyelles nasales, `rang_dans_mot` désigne celle à annoter (1 = la première nasale du mot).
3. Écouter le mot, puis la voyelle seule (sélection à la souris, touche Tab), de préférence au casque.

### `nature`

| Code | Signification |
| --- | --- |
| `N` | voyelle nasale du début à la fin, sans consonne nasale distincte après |
| `ON` | voyelle orale suivie d'une consonne nasale distincte ([n], [m], [ŋ]) |
| `O` | voyelle orale, sans nasalité perçue |
| `?` | indécidable (bruit, chevauchement, voyelle trop brève, alignement faux) |

Sur le spectrogramme, une consonne nasale se reconnaît à une chute brusque d'énergie, avec presque uniquement des basses fréquences et des bords nets (`ON`). Une voyelle nasale garde des formants nets mais affaiblis, surtout F1, avec de l'énergie supplémentaire dans les basses fréquences et sans coupure nette (`N`). Une voyelle orale a des formants nets, sans énergie particulière dans les basses fréquences (`O`).

### `deb_manuel` et `fin_manuel`

Sélectionner la partie vocalique à la souris, puis relever les temps avec *Query > Get start of selection* et *Get end of selection*, en secondes (ex. `41.253`). Garder le même critère pour toutes les voyelles, par exemple : début au premier cycle régulier après la consonne précédente, fin quand la structure des formants disparaît ou change nettement.

### `f1_manuel` et `f2_manuel`

1. Activer *Formant > Show formants*.
2. Garder la voyelle sélectionnée du début à la fin.
3. Utiliser *Formant > Get first formant* puis *Get second formant* : Praat affiche « mean F1 in SELECTION », donc la moyenne sur toute la voyelle. Recopier les valeurs en Hz.
4. Si les points rouges ne suivent pas les bandes sombres du spectrogramme, modifier le plafond (*Formant > Formant settings…*, par exemple 5000 ou 6000), refaire la mesure et noter le plafond dans `commentaire`.

Si une mesure est impossible, laisser la case vide et en indiquer la raison en commentaire.

### `commentaire`

Texte libre : bruit, chevauchement, voix craquée, plafond modifié, doute… Les mots « alignement » et « transcription » y sont repérés par le script de comparaison pour compter les problèmes signalés.

## 3. Comparer

Enregistrer la feuille sous le même nom, fermer Excel, puis :

```bash
python scripts/comparer_manuel_auto.py
```

Les virgules décimales d'Excel en français sont acceptées. Résultats dans `resultats/` :

| Fichier | Contenu |
| --- | --- |
| `par_locutrice.csv` / `.xlsx` | comparaison des locutrices |
| `par_voyelle.csv` / `.xlsx` | détail par timbre de voyelle nasale |
| `detail.csv` | une ligne par voyelle annotée |
| `comparaison.png` | F1 et F2 automatiques contre manuels, écart des bornes, jugement de nature |
| `par_voyelle.png` | voyelles non confirmées nasales et alignement, par timbre |

### Indicateurs

- **Bien alignée** : le milieu de la voyelle manuelle tombe dans l'intervalle posé par WebMAUS. Les écarts de bornes et de formants ne sont calculés que sur ces voyelles : pour les autres, la machine a mesuré un autre son.
- **Écart de bornes** : écart absolu médian (ms) ; part des voyelles dont les deux bornes sont à 20 ms ou moins.
- **Écart de formants** : erreur absolue moyenne (Hz) sur F1 et F2 entre la moyenne manuelle et `f1Moy` / `f2Moy` ; part des mesures à 100 Hz (F1) ou 200 Hz (F2) ou moins.
- **Nature** : effectifs `N`, `ON`, `O`, `?` ; part des voyelles non confirmées nasales (`ON` + `O` + `?`).
- **Problèmes signalés** : voyelles dont le commentaire mentionne l'alignement ou la transcription.

Les seuils se règlent en tête de `comparer_manuel_auto.py`. Les saisies incohérentes (fin avant le début, durée supérieure à 1 s) sont signalées et leurs bornes ignorées. Par timbre, une alerte signale les groupes de moins de 5 voyelles, dont les pourcentages ne sont pas interprétables.

## Dépannage

| Message ou symptôme | Cause probable |
| --- | --- |
| `Aucun fichier resultat_*.txt` | les résultats de l'extraction ne sont pas dans `donnees/` |
| `PermissionError` | un fichier Excel est ouvert |
| `La feuille d'annotation est vide` | aucune colonne remplie, ou feuille enregistrée sous un autre nom |
| `[saisie à vérifier] …` | fin avant le début, ou durée supérieure à 1 s : corriger la feuille et relancer |
| `aucune ligne pour la référence …` | le nom de la locutrice native diffère : utiliser `--reference` |
| Les temps ne tombent pas sur le bon mot | l'audio et le TextGrid ne correspondent pas |
