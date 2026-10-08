---
schema_version: base.resource.v1
id: importer-l-existant
type: process
title: Importer l'existant
scope: personal
status: active
sensitivity: internal
description: Convertir vos documents existants (notes, modes d'emploi, wikis, checklists) en ressources BASE (process, compétences, documents, templates), proposées via le gate, jamais écrites d'office.
use_when: Quand l'utilisateur veut partir de ses documents existants: «importe mes procédures», «transforme ce mode d'emploi en process», «j'ai déjà tout dans un wiki».
keywords: [import, migration, conversion, existant, onboarding]
routing:
  examples:
    - Importer mes procédures existantes
    - Transformer ce document en process
    - J'ai déjà un wiki, comment le réutiliser?
  avoid_when:
    - Signaler un dysfonctionnement de l'assistant.
    - Faire le point sur un dossier en service et dire ce qui pourrait aller mieux dans ses process.
user-invocable: true
---

# Importer l'existant

Personne ne part d'une page blanche: le savoir-faire est déjà dans des documents. Ce process
explore ce que vous pointez et PROPOSE des conversions en ressources BASE; chaque écriture passe
par le gate (proposer puis valider), vous validez chaque diff.

Si la personne veut d'abord voir ce qu'un assistant ferait pour elle, avant toute conversion
(«montre-moi ce que BASE en ferait», «ne change encore rien»), suis `adopter-ce-dossier`, un process
du cadre BASE atteint via `framework_dir`: il rend une fiche de proposition à relire dans le
navigateur, et l'import reprend ici, à l'étape 3, avec la carte tirée de son export.

Au premier échange, ne récite ni les étapes ni les catégories ci-dessous. Dis en trois phrases
au plus que tu es prêt, que rien ne sera écrit sans validation, puis demande où sont les documents.

## Étapes

1. **Explorer le matériau.** Lis chaque source indiquée. Classe chaque contenu: ce qui *se suit*
   (étapes, checklist) devient un `process`; ce qui *s'apprend* (règles, conventions) une
   `competence` ou un `document`; ce qui *se remplit* (trame, modèle) un `template`; ce qui *se
   consulte avec une validité* (barème, tarifs) un `document` daté.
   Une règle déjà écrite pour l'IA (un `CLAUDE.md`, des règles d'outil) ne se recopie pas si un
   modèle l'applique de lui-même; une règle propre à la maison se garde; une règle dont un seul manquement coûterait cher reçoit un verrou
   (l'information mise hors d'atteinte, ou une permission de l'outil avec son bac à sable), essayé une
   fois sans conséquence, par chaque chemin: l'outil d'écriture, une commande, une copie.
2. **Proposer la carte d'import.** Présente la découpe source vers ressource cible (type, id,
   chemin) et fais-la valider AVANT toute conversion. Reste flexible: guide une migration
   progressive vers une structure exploitable par l'IA, et propose d'ajouter ce qui est utile.
3. **Convertir, une ressource à la fois.** Rédige le fichier complet (frontmatter id, type, title,
   description, un `use_when` digne du routeur) et propose-le. Ne committe jamais toi-même: l'humain
   valide chaque diff.
4. **Vérifier la santé après import.** Recommande `base doctor`: il relève les liens cassés par la
   copie et les ressources orphelines.

## Ce que tu ne fais jamais

- Écrire sans diff validé. Proposer, toujours; committer, jamais.
- Inventer du contenu absent des sources. Tu convertis, tu ne crées pas de savoir.
- Importer en vrac. Chaque ressource est découpée, nommée et validée une à une.
