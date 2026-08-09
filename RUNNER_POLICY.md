# Politique des runners VenaLabs

Tous les workflows des dépôts privés utilisent par défaut
`[self-hosted, venalabs-ci]`. Les actions distantes sont épinglées par SHA et les
permissions d'écriture sont refusées sauf besoin explicite.

Les exceptions sont centralisées dans
`.github/runner-policy-exceptions.json`. Chacune nomme le dépôt, le workflow,
le job, sa justification et sa date d'expiration. Une exception expirée fait
échouer la politique.

Le modèle `workflow-templates/venalabs-ci.yml` sert de point de départ aux
nouveaux projets. Le ruleset d'organisation exige le workflow
`VenaLabs runner policy` avant toute fusion sur une branche par défaut.

Les dépôts publics et les tests exigeant macOS ou Windows ne doivent pas
utiliser le pool Linux persistant. Ils nécessitent une exception approuvée avant
activation.
