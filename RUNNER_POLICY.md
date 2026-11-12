# Politique des runners VenaLabs

Tous les workflows des dépôts privés utilisent par défaut
`[self-hosted, venalabs-ci]`. Les actions distantes sont épinglées par SHA et les
permissions d'écriture sont refusées sauf besoin explicite.

Les tests, builds et scans Linux utilisent les six listeners du pool partagé.
Les opérations Finance qui manipulent les clés de déploiement utilisent des VM
`ubuntu-24.04` éphémères : décision de Marvin du 12 novembre 2026. Les tâches courtes
d'orchestration utilisent `ubuntu-slim` avec une exception nominative et datée.
Les builds Xcode conservent leur exception native ; aucune émulation Linux ne les
remplace. Le budget Actions bloque tout dépassement payant à 0 $ : le quota inclus
épuisé suspend les jobs hébergés, sans repli automatique payant.

Les exceptions sont centralisées dans
`.github/runner-policy-exceptions.json`. Chacune nomme le dépôt, le workflow,
le job, sa justification et sa date d'expiration. Une exception expirée fait
échouer la politique.

Le modèle `workflow-templates/venalabs-ci.yml` sert de point de départ aux nouveaux
projets. Le workflow réutilisable `runner-policy.yml`, appelé par SHA depuis chaque
dépôt, analyse le YAML réel : listes multilignes, permissions héritées, références
d'actions et de workflows réutilisables, doublons de clés, timeouts et placements.
Le code de la politique est lui-même épinglé ; le dépôt contrôlé n'est jamais exécuté
par ce job et les jetons de checkout ne sont pas conservés.

Le plan GitHub Free actuel ne fournit pas de ruleset requis pour les dépôts privés.
Le check rend un verdict, mais **ne verrouille pas le bouton de fusion**. La revue
doit vérifier les checks du dernier SHA avant de fusionner. Une règle d'organisation
ne doit pas être annoncée comme active tant qu'elle n'existe pas réellement.

Chaque job lourd borne ses workers (par défaut deux) et son timeout. Les bases de
test utilisent des ports hôtes aléatoires, les projets Docker et images un nom lié
au run. Aucun nettoyage global de volumes ou réseaux n'est permis depuis un job.
Un runner privé persistant avec accès Docker n'est pas une frontière de sécurité
entre projets : ce pool reste réservé au code interne de confiance.

La supervision des VPS est extérieure au pool, toutes les cinq minutes, avec
alerte e-mail après trois échecs consécutifs et au rétablissement. Les canaris
GitHub prouvent l'exécution d'un job ; leur temps en file n'est pas une panne.

Les dépôts publics et les tests exigeant macOS ou Windows ne doivent pas
utiliser le pool Linux persistant. Ils nécessitent une exception approuvée avant
activation.
