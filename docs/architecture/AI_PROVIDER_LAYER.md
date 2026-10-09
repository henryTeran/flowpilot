# Couche de fournisseurs IA

Référence : phase 19 du Master Plan et ADR-002. Les fournisseurs implémentent des contrats d’infrastructure; les modules métier conservent les faits, permissions, scopes, calculs et autorisations d’action.

## Checkpoint 19A : contrats et fournisseurs offline

`app.ai.contracts` définit `LLMProvider.complete`, `SpeechToTextProvider.transcribe` et `EmbeddingProvider.embed`, avec DTO indépendants de tout SDK. Messages, résultats textuels/JSON, audio et vecteurs sont bornés. Les vecteurs doivent avoir des dimensions identiques et finies et couvrir chaque texte demandé. Les rôles sont fermés et les champs supplémentaires refusés. Le schéma de sortie optionnel décrit le format demandé; le consommateur doit toujours vérifier le sens et le contrat métier du résultat.

`app.ai.boundary` reconstruit les entrées et sorties, y compris les modèles créés avec une copie non validée. L’audio conserve ses octets, sans conversion JSON destructive. Les limites sont des limites de transport applicatives (caractères/octets/éléments), pas une estimation du tokenizer ou une validation de format audio décodé.

Les timeouts et indisponibilités deviennent des exceptions stables sans détails privés dans leur message public; les réponses malformées sont distinctement refusées. La frontière ne journalise pas les prompts, l’audio, les sorties ou les secrets. Aucune proposition de texte/JSON, transcription ou similarité ne prouve l’identité, les permissions, la vérité d’un fait ou l’autorisation d’exécuter une action. Les garde-fous BASE/JV et métier restent nécessaires au consommateur.

`app.ai.fake` fournit trois implémentations scriptées, utilisables sans credentials, réseau, SDK ou accès métier. Elles permettent des tests offline de succès, silence, panne, timeout, réponse hostile, faux champs d’autorité, copies non vérifiées et vecteurs invalides.

Validation : **20 tests réussis en 4,77 s**, zéro échec/skip, incluant les contrats providers, les contributions JV et le noyau opérationnel avec capture BASE réelle. Les avertissements sont la dépréciation Starlette existante et les constructions volontairement invalides de tests. Aucun SDK, requête distante, décodage audio réel, embedding sémantique ou performance de modèle n’est revendiqué à ce checkpoint.

## Checkpoint 19B : adaptateur OpenAI Responses/embedding

`app.ai.openai_adapter` est le seul module applicatif important le SDK OpenAI, verrouillé à `2.54.0`. Il reçoit un client et deux noms de modèle explicitement configurés côté serveur; aucun modèle par défaut implicite ni activation distante dans les routes métier n’est ajouté.

Le port LLM utilise l’API Responses avec messages typés, limite de sortie, outils vides et `store=false`. Le schéma optionnel passe dans `text.format` en mode JSON Schema strict. Les réponses incomplètes, refus, appels d’outil inattendus, JSON malformé et sorties de forme incorrecte sont refusés. Le port embedding demande des vecteurs float, rétablit l’ordre des textes via les indices et refuse indices manquants/dupliqués/non entiers ou vecteurs invalides. Le consommateur vérifie toujours le contrat métier; l’adaptateur ne transforme pas un texte en autorisation.

Références officielles consultées le 9 octobre 2026 : [Responses Python](https://developers.openai.com/api/reference/python/resources/responses/methods/create), [Embeddings Python](https://developers.openai.com/api/reference/python/resources/embeddings/methods/create). `store=false` décrit le paramètre d’état de l’API, sans constituer une garantie universelle de rétention des données.

Validation SDK réel et `httpx.MockTransport`, sans réseau : première exécution 16 réussis; finale après refus/401/indices entiers, **18 réussis en 2,60 s**, zéro échec/skip. Les tests vérifient sérialisation des requêtes, parsing réel SDK, structured JSON, réponses partielles/hostiles, timeout/401 normalisés et un seul appel avec client timeout 5 s/retries 0, ordre des embeddings et doublons. Les clients de test sont fermés. La frontière commune préserve désormais la catégorie réponse invalide remontée par un adaptateur. Aucun crédit distant, credential réel, transcription OpenAI, configuration de déploiement ou qualification de modèle n’est revendiqué.

## Acceptation restante

La phase reste **PARTIAL**. OpenAI LLM/embedding est isolé et testé; Voxtral, sélection/configuration serveur de runtime, transcription et acceptation de phase restent ouverts. Aucun import SDK ne doit être introduit dans les modules métier. La qualification distante et les credentials de déploiement restent des preuves distinctes des contrats offline.
