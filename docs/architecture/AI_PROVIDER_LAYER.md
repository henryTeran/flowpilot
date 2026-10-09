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

## Checkpoint 19C : transcription Voxtral isolée

`app.ai.voxtral_adapter` est le seul module applicatif important Mistral, verrouillé à `mistralai==3.2.0`. Il implémente le port de transcription avec modèle serveur explicite, timeout borné et retries désactivés pour chaque opération. Il utilise `httpx2`, la bibliothèque effective de cette version SDK, pour identifier correctement ses timeouts.

Les octets validés sont envoyés au SDK en multipart avec un nom de fichier constant dérivé du type média. Aucun chemin local, URL de fichier, file ID, contexte métier ou instruction générée n’est accepté dans le contrat audio. Langue explicite optionnelle, diarisation désactivée; seule la transcription textuelle typée est rendue. Une chaîne vide peut représenter le silence; une réponse malformée ne devient pas une chaîne vide inventée. Timeouts, erreurs HTTP et erreurs de parsing SDK sont normalisés. L’adaptateur possède le client injecté et le ferme explicitement.

Référence officielle consultée le 9 octobre 2026 : [API de transcription Mistral](https://docs.mistral.ai/api/endpoint/audio/transcriptions). Les signatures, bibliothèque HTTP et gestion de fermeture ont également été vérifiées dans le SDK installé. Le checkpoint ne revendique ni décodage audio local, ni transcription sémantique réelle, ni qualification d’un modèle distant.

L’installation dans le chemin long de l’environnement du dépôt a échoué sur MAX_PATH. Un environnement Python 3.13 standard séparé, au chemin court `C:/Users/CorralesSusana/.codex/cache/flowpilot-ai19`, installe tous les requirements et SDK sans changer les réglages Windows. Cet environnement devient la référence de validation providers Windows; l’ancien cache d’installation partielle n’est pas présenté comme réparé.

Premiers tests avec SDK réel et transport simulé : **22 réussis en 5,61 s**. Validation finale avec transport natif `httpx2` et parsing malformé : **24 réussis en 4,13 s**, zéro échec/skip, incluant OpenAI et les contrats/fakes. Multipart binaire exact, modèle/langue, silence, timeout/401 avec un seul appel, réponse invalide, refus avant upload et fermeture du client sont vérifiés. Aucune requête réseau de modèle ni credential réel n’est utilisé. Les avertissements sont des dépréciations AST d’une dépendance SDK et la copie Pydantic volontairement invalide d’un test.

## Checkpoint 19D : sélection serveur et cycle de vie

`app.ai.runtime.AISettings` lit exclusivement l’environnement serveur préfixé `FLOWPILOT_AI_`. Les trois ports ont des sélecteurs fermés et sont désactivés par défaut. Une sélection OpenAI/Voxtral nécessite ses modèles explicitement nommés et ses credentials `SecretStr`; aucune clé, modèle ou URL de fournisseur ne vient d’un corps HTTP. Le timeout partagé est borné de 1 à 60 000 ms. Le fichier exemple donne les variables désactivées : Compose les exporte via son env_file existant; un lancement uvicorn direct doit les exporter dans le processus. Ce Settings ne lit pas implicitement le fichier `.env`.

La factory importe les SDK uniquement lorsqu’ils sont sélectionnés, fixe les endpoints officiels, timeout et retries 0/None, et n’utilise pas les réglages de proxy/endpoint hérités implicitement par les clients HTTP. OpenAI LLM et embedding partagent un client; chaque port peut être sélectionné séparément sans exiger de modèle inutilisé. Le mode fake exige un binding serveur explicite, emprunté à son propriétaire; il n’invente pas une sortie de modèle par défaut.

Le lifespan FastAPI construit les fournisseurs après les contrôles de bootstrap existants, les place dans l’état serveur et ferme les clients possédés à l’arrêt. La construction partielle ferme les ressources déjà créées. La fermeture est idempotente et tente toutes les ressources, même après un échec, puis signale un échec nettoyé sans détail privé. Aucun appel distant n’est effectué par les constructeurs. Les interfaces métier restent disponibles avec ports désactivés et la sélection n’active pas encore une route de génération ou transcription.

Validation Windows : régression runtime/ports/OpenAI/Voxtral/noyau JV **35 réussis en 15,06 s**, zéro échec/skip. Les tests complétés de lifespan et binding fake : **7 réussis en 3,77 s**. Contrôles de démarrage existants : **2 réussis en 0,26 s**. La construction SDK réelle sans requête vérifie clients partagés, endpoints explicites, credentials masqués et fermeture; factories simulées vérifient rollback partiel et nettoyage après erreur. Le lifespan réel vérifie installation/fermeture d’un fournisseur possédé. Aucune validation d’inférence distante, proxy de déploiement, qualité de modèle ou image Linux mise à jour n’est revendiquée ici.

## Acceptation restante de la phase

La phase reste **PARTIAL** en attente de l’image Linux et de l’audit final. OpenAI LLM/embedding, Voxtral STT, sélection serveur et lifecycle sont implémentés et testés. Les SDK restent dans `app.ai`. La qualification distante et les credentials de déploiement restent des preuves distinctes des contrats offline.
