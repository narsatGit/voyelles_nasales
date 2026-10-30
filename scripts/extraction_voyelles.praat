# extraction_voyelles.praat
#
# Extrait les voyelles orales et nasales d'un enregistrement aligné par WebMAUS :
# mot, durée, contexte, F1, F2 et f0 de chaque voyelle.
#
# Script d'origine : Cours linguistique du corpus 2024 L3 SDL UNICAEN.
# Adapté et étendu avec l'appui de Claude AI (Anthropic).
#
# Entrées : <nom>.wav et <nom>.TextGrid (tiers 1 ORT-MAU, 2 KAN-MAU, 3 MAU ; étiquettes SAMPA)
# Sortie  : resultat_<nom>.txt (séparateur tabulation, NA pour une valeur indéfinie)
#
# Colonnes :
#   debPhone, finPhone, labPhone, type (orale / nasale), labMot, duree, precedent, suivant
#   f1, f2         formants au milieu de la voyelle (Hz)
#   f1Moy, f2Moy   formants moyennés sur toute la voyelle (Hz), comme « mean F1 in SELECTION » de Praat
#   f0, f0Moy      f0 au milieu et moyennée sur la moitié centrale de la voyelle (Hz)
#   exploitable    1 si la durée atteint duree_min et si F1 et F2 sont définis

form Extraction des voyelles
	comment Dossier du .wav et du .TextGrid (chemin relatif au dossier du script, ou chemin complet)
	sentence dossier ../donnees
	comment Nom commun aux deux fichiers, sans extension
	sentence nom russophone
	comment Plafond des formants en Hz (voix féminine : 5500)
	positive plafond_formants 5500
	comment Limites de la f0 en Hz (voix féminine : 100 à 500)
	positive plancher_f0 100
	positive plafond_f0 500
	comment Durée minimale (en secondes) pour qu'une voyelle soit marquée exploitable
	positive duree_min 0.04
endform

# --- Procédure : écrit un nombre avec n décimales, ou NA s'il est indéfini ---
procedure formater: .x, .nd
	if .x = undefined
		formate$ = "NA"
	else
		formate$ = fixed$ (.x, .nd)
	endif
endproc

# --- Paramètres du TextGrid ---
iMot = 1
iPhone = 3

voyellesOrales$ = " a e E i o O u y 2 9 "
voyellesNasales$ = " a~ e~ o~ 9~ "

# --- Lecture des fichiers ---
son = Read from file: dossier$ + "/" + nom$ + ".wav"
tg = Read from file: dossier$ + "/" + nom$ + ".TextGrid"

# --- Vérifications ---
selectObject: tg
nomTier$ = Get tier name: iPhone
if nomTier$ <> "MAU"
	exitScript: "Le tier " + string$ (iPhone) + " s'appelle '" + nomTier$ + "' et non 'MAU'. Vérifiez la valeur de iPhone."
endif

selectObject: son
dureeSon = Get total duration
selectObject: tg
dureeTg = Get total duration
writeInfoLine: "Extraction de ", nom$
if abs (dureeSon - dureeTg) > 1
	appendInfoLine: "ATTENTION : le son dure ", fixed$ (dureeSon, 1), " s mais le TextGrid ", fixed$ (dureeTg, 1), " s. Vérifiez que ce sont bien les mêmes fichiers."
endif

# --- Analyses acoustiques ---
selectObject: son
pitch = To Pitch: 0, plancher_f0, plafond_f0

selectObject: son
formants = To Formant (burg): 0, 5, plafond_formants, 0.025, 50

# --- Intervalles du tier des phones ---
selectObject: tg
nbPhones = Get number of intervals: iPhone

fichierResultats$ = dossier$ + "/resultat_" + nom$ + ".txt"
writeFileLine: fichierResultats$, "debPhone", tab$, "finPhone", tab$, "labPhone", tab$, "type", tab$, "labMot", tab$, "duree", tab$, "precedent", tab$, "suivant", tab$, "f1", tab$, "f1Moy", tab$, "f2", tab$, "f2Moy", tab$, "f0", tab$, "f0Moy", tab$, "exploitable"

nbEcrites = 0

for iIntv from 1 to nbPhones

	selectObject: tg
	labPhone$ = Get label of interval: iPhone, iIntv

	# Voyelle nasale, orale, ou autre chose (consonne, pause...)
	if index (voyellesNasales$, " " + labPhone$ + " ") > 0
		type$ = "nasale"
	elsif index (voyellesOrales$, " " + labPhone$ + " ") > 0
		type$ = "orale"
	else
		type$ = ""
	endif

	if type$ <> ""

		debPhone = Get start time of interval: iPhone, iIntv
		finPhone = Get end time of interval: iPhone, iIntv
		duree = finPhone - debPhone
		tempsMil = debPhone + duree / 2

		# moitié centrale de la voyelle (de 25 % à 75 %), utilisée seulement pour la f0 moyenne (f0Moy)
		debCentre = debPhone + duree / 4
		finCentre = finPhone - duree / 4

		# mot contenant la voyelle
		nbIntMot = Get interval at time: iMot, tempsMil
		labMot$ = Get label of interval: iMot, nbIntMot

		# contexte
		precedent$ = ""
		if iIntv > 1
			precedent$ = Get label of interval: iPhone, iIntv - 1
		endif
		suivant$ = ""
		if iIntv < nbPhones
			suivant$ = Get label of interval: iPhone, iIntv + 1
		endif

		# f0
		selectObject: pitch
		f0 = Get value at time: tempsMil, "Hertz", "linear"
		f0Moy = Get mean: debCentre, finCentre, "Hertz"

		# formants : valeur au milieu (f1, f2) et moyenne sur toute la voyelle (f1Moy, f2Moy),
		# c'est-à-dire ce que Praat affiche (« mean F1 in SELECTION ») quand on sélectionne la voyelle
		selectObject: formants
		f1 = Get value at time: 1, tempsMil, "hertz", "linear"
		f2 = Get value at time: 2, tempsMil, "hertz", "linear"
		f1Moy = Get mean: 1, debPhone, finPhone, "hertz"
		f2Moy = Get mean: 2, debPhone, finPhone, "hertz"

		# exploitable : durée suffisante et formants mesurés
		exploitable = 0
		if duree >= duree_min - 0.0001 and f1 <> undefined and f2 <> undefined
			exploitable = 1
		endif

		# écriture d'une ligne
		ligne$ = fixed$ (debPhone, 4) + tab$ + fixed$ (finPhone, 4) + tab$ + labPhone$ + tab$ + type$ + tab$ + labMot$ + tab$ + fixed$ (duree, 4) + tab$ + precedent$ + tab$ + suivant$

		@formater: f1, 1
		ligne$ = ligne$ + tab$ + formate$
		@formater: f1Moy, 1
		ligne$ = ligne$ + tab$ + formate$
		@formater: f2, 1
		ligne$ = ligne$ + tab$ + formate$
		@formater: f2Moy, 1
		ligne$ = ligne$ + tab$ + formate$
		@formater: f0, 1
		ligne$ = ligne$ + tab$ + formate$
		@formater: f0Moy, 1
		ligne$ = ligne$ + tab$ + formate$
		ligne$ = ligne$ + tab$ + string$ (exploitable)

		appendFileLine: fichierResultats$, ligne$
		nbEcrites = nbEcrites + 1

	endif
endfor

appendInfoLine: nbEcrites, " voyelles écrites dans ", fichierResultats$

removeObject: son, tg, pitch, formants
