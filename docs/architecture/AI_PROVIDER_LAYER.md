# Couche de fournisseurs IA

Référence : phase 19 du Master Plan et ADR-002. Les fournisseurs implémentent des contrats d’infrastructure; les modules métier conservent les faits, permissions, scopes, calculs et autorisations d’action.

## Checkpoint 19A : contrats et fournisseurs offline

`app.ai.contracts` définit `LLMProvider.complete`, `SpeechToTextProvider.transcribe` et `EmbeddingProvider.embed`, avec DTO indépendants de tout SDK. Messages, résultats textuels/JSON, audio et vecteurs sont bornés. Les vecteurs doivent avoir des dimensions identiques et finies et couvrir chaque texte demandé. Les rôles sont fermés et les champs supplémentaires refusés. Le schéma de sortie optionnel décrit le format demandé; le consommateur doit toujours vérifier le sens et le contrat métier du résultat.

`app.ai.boundary` reconstruit les entrées et sorties, y compris les modèles créés avec une copie non validée. L’audio conserve ses octets, sans conversion JSON destructive. Les limites sont des limites de transport applicatives (caractères/octets/éléments), pas une estimation du tokenizer ou une validation de format audio décodé.

Les timeouts et indisponibilités deviennent des exceptions stables sans détails privés dans leur message public; les réponses malformées sont distinctement refusées. La frontière ne journalise pas les prompts, l’audio, les sorties ou les secrets. Aucune proposition de texte/JSON, transcription ou similarité ne prouve l’identité, les permissions, la vérité d’un fait ou l’autorisation d’exécuter une action. Les garde-fous BASE/JV et métier restent nécessaires au consommateur.

`app.ai.fake` fournit trois implémentations scriptées, utilisables sans credentials, réseau, SDK ou accès métier. Elles permettent des tests offline de succès, silence, panne, timeout, réponse hostile, faux champs d’autorité, copies non vérifiées et vecteurs invalides.

Validation : **20 tests réussis en 4,77 s**, zéro échec/skip, incluant les contrats providers, les contributions JV et le noyau opérationnel avec capture BASE réelle. Les avertissements sont la dépréciation Starlette existante et les constructions volontairement invalides de tests. Aucun SDK, requête distante, décodage audio réel, embedding sémantique ou performance de modèle n’est revendiqué à ce checkpoint.

## Suite et gates

La phase reste **PARTIAL**. Les ports et faux fournisseurs sont implémentés; `OPENAI_ISOLATED` et `VOXTRAL_ISOLATED` restent manquants. La suite ajoute les adaptateurs spécifiques dans `app.ai`, sélection/configuration serveur explicites, timeouts et tests de transport mocké via les SDK réels. Aucun import SDK ne doit être introduit dans les modules métier. La qualification distante et les credentials de déploiement restent des preuves distinctes des contrats offline.
