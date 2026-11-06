# Résumé des résultats — couverture paramétrique séisme

## Qu'a-t-on simulé ?

Le script a généré **200 000 années fictives** de séismes. Pour chaque événement, il simule une magnitude et une distance, puis estime un indice d'accélération du sol (PGA) avec une relation simplifiée. Le contrat verse ensuite 25 %, 50 % ou 100 % de sa limite selon le seuil PGA atteint. Les paiements de plusieurs séismes sont additionnés par année et plafonnés à 10 M$.

Le catalogue, la relation PGA et les paramètres sont stylisés. Les chiffres ci-dessous expliquent le fonctionnement du modèle, pas le risque réel d'un pays ou d'un portefeuille.

## Quel prix le modèle obtient-il ?

L'indemnité annuelle moyenne (AAL) est de **88 475 $**. La prime dite « principe de l'écart-type » ajoute à cette moyenne une marge de 35 % de l'écart-type des paiements :

```text
88 475 $ + 35 % × 639 032 $ = 312 136 $
```

Rapportée à la limite annuelle de 10 M$, cette prime correspond à un rate on line de **3,12 %**. Le contrat paie dans **2,518 %** des années simulées.

La VaR 99 % vaut **2,5 M$** : 99 % des années ont un paiement inférieur ou égal à ce montant. La TVaR 99 % vaut **5,05 M$** : c'est le paiement moyen dans les 1 % d'années les plus coûteuses. Comme la distribution des paiements est discrète, la TVaR est calculée sur exactement 1 % des observations, y compris en présence d'ex æquo à la VaR.

## Le contrat reflète-t-il bien les pertes ?

Le modèle simule aussi une perte économique hypothétique, séparée de l'indice PGA contractuel. La corrélation entre perte et indemnité est de **0,682** : l'indice donne une information sur la perte, mais il ne la reproduit pas parfaitement.

- Dans **1,395 %** des années, le contrat paie alors que la perte simulée reste sous le seuil « matériel » choisi (5 % de la limite).
- Dans **0,238 %** des années, une perte dépasse ce seuil sans paiement du contrat.
- La perte matérielle et l'indemnité sont définies par des fonctions stylisées; ces fréquences sont propres à ces hypothèses.

Ce décalage est le **basis risk** : une couverture indexée peut payer trop, pas assez, ou ne pas payer malgré une perte.

## Les paramètres changent-ils beaucoup le prix ?

Le programme crée 200 catalogues fictifs de 60 ans, réestime la fréquence des séismes et la b-value, puis recalcule la prime. Les percentiles 5 et 95 sont **258 487 $** et **378 946 $** (coefficient de variation : **11,6 %**). Cela illustre l'incertitude associée à l'estimation de paramètres sur un historique court.

Les scénarios de sensibilité font varier une hypothèse à la fois. Le coefficient d'atténuation c2 de la GMPE a l'effet le plus marqué : la prime change de **−22,7 % à +39,2 %** dans les cas testés. σ de la GMPE produit des écarts de **−16,2 % à +19,2 %**. Ces amplitudes ne sont pas des intervalles de confiance; elles dépendent des scénarios choisis.

## Comment lire la frontière des triggers ?

Le balayage compare des contrats binaires qui paient toute la limite dès que le PGA dépasse un seuil. Dans la grille calculée, relever le seuil diminue le coût et les paiements injustifiés, mais augmente la fréquence des pertes matérielles sans paiement. Le taux des deux types d'erreur change d'ordre entre **0,12 g et 0,16 g**; la grille n'est pas assez fine pour estimer un point d'égalité.

## Conclusion

Le travail démontre une chaîne de modélisation et de pricing paramétrique, et met en évidence le poids du choix de l'indice, de ses seuils et de l'incertitude de la GMPE. La conclusion pratique principale est que le chiffre de prime est très dépendant des hypothèses d'aléa : avant tout usage réel, il faudrait calibrer sur un catalogue d'événements et une GMPE publiés pour une région donnée, puis valider la vulnérabilité du portefeuille.

## Fichiers sources des chiffres

- `summary.json` : métriques principales.
- `sensitivity.csv` : scénarios de sensibilité.
- `trigger_frontier.csv` : seuils binaires et erreurs associées.
- `ep_curve.csv` : quantiles par période de retour.
