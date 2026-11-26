# Guide de test du portail (lots 1 et 2)

Ce guide permet de dérouler tout le parcours en une vingtaine de minutes, sur un poste ou dans le navigateur avec GitHub Codespaces. Les données sont fictives et la base est un simple fichier SQLite.

## 1. Lancer le portail

### Option A : sans rien installer (GitHub Codespaces)

1. Sur GitHub, ouvrez le dépôt `portail-prestataires` et choisissez la branche `lot-2-habilitations`, qui contient les lots 1 et 2.
2. Cliquez sur **Code**, ouvrez l'onglet **Codespaces**, puis **Create codespace on lot-2-habilitations**.
3. Dans le terminal du Codespace, tapez :

```bash
pip install -r requirements.txt
export PORTAIL_DEBUG=1
export PORTAIL_ALLOWED_HOSTS='*'
export PORTAIL_CSRF_TRUSTED_ORIGINS="https://${CODESPACE_NAME}-8000.app.github.dev"
python manage.py migrate
python manage.py charger_demo
python manage.py runserver 0.0.0.0:8000
```

4. Codespaces propose d'ouvrir le port 8000 dans le navigateur : acceptez.

### Option B : sur un poste avec Python 3.12 ou plus

```bash
git clone https://github.com/f6yswk7fhy-rgb/portail-prestataires.git
cd portail-prestataires
git checkout lot-2-habilitations
python3 -m venv .venv && . .venv/bin/activate      # Windows : .venv\Scripts\activate
pip install -r requirements.txt
export PORTAIL_DEBUG=1                              # Windows PowerShell : $env:PORTAIL_DEBUG="1"
python manage.py migrate
python manage.py charger_demo
python manage.py runserver
```

Ouvrez ensuite http://127.0.0.1:8000.

> Docker (`docker compose`) sert au déploiement réel avec PostgreSQL : il refuse le mode démonstration. Pour tester, utilisez l'option A ou B.

## 2. Comptes de démonstration

| Rôle | Email | Mot de passe |
| --- | --- | --- |
| Prestataire (MédiSoft) | thomas.girard@demo.invalid | Demo-prestataire-2026 |
| RSSI | rssi@demo.invalid | Demo-interne-2026 |
| DSI | dsi@demo.invalid | Demo-interne-2026 |
| Référent interne | referent@demo.invalid | Demo-interne-2026 |
| Référent applicatif du PACS | pacs@demo.invalid | Demo-interne-2026 |
| Référent technique | technicien@demo.invalid | Demo-interne-2026 |

**MFA** : à la première connexion, chaque compte affiche un QR code. Scannez-le avec Microsoft Authenticator, Google Authenticator ou FreeOTP : une même application peut contenir les six comptes. En production, le personnel passera par Entra ID et n'aura pas cette étape.

Pour passer d'un rôle à l'autre, utilisez **Se déconnecter**, ou ouvrez une fenêtre de navigation privée par rôle.

## 3. Parcours complet

| Étape | Qui | Quoi faire | Résultat attendu |
| --- | --- | --- | --- |
| 1 | referent@ | **Habilitations**, puis **Nouvelle habilitation**. Saisissez un nouvel intervenant (votre propre email de test, une nouvelle société), l'application « PACS imagerie (démo) », une date de fin dans 3 mois et une justification. | Habilitation « Charte à signer ». L'email d'invitation s'affiche dans le terminal, avec un lien personnel. |
| 2 | Nouvel intervenant | Ouvrez le lien d'invitation affiché dans le terminal (remplacez le début par l'adresse du portail si besoin). Choisissez un mot de passe, puis scannez le QR code. | Accueil « Signature de la charte requise ». |
| 3 | Nouvel intervenant | **Lire et signer la charte**. Faites défiler la charte jusqu'au bout, cochez l'engagement, puis saisissez le code MFA. | « Charte v1.0 signée », avec la preuve. L'habilitation passe « En validation RSSI ». |
| 4 | rssi@ | **Habilitations**, ouvrez la demande, puis **Valider l'habilitation**. Essayez aussi de refuser sans motif : c'est bloqué. | Statut « Compte en préparation ». |
| 5 | technicien@ | **Tâches techniques**, « Créer le compte dans BeyondTrust », puis **C'est fait**. | Habilitation « Dormante ». |
| 6 | Intervenant | **Mes accès**, ouvrez l'habilitation, puis **Demander une intervention** (motif et créneau de moins de 8 h). Essayez 9 h : c'est refusé. | Intervention « À valider ». |
| 7 | pacs@ | **Habilitations**, puis, dans « Interventions à valider », **Valider**. | Intervention « Ouverture en attente ». |
| 8 | technicien@ | **Tâches techniques**, « Activer le compte AD », puis **C'est fait**. | Intervention « Accès ouvert ». Une tâche « Désactiver le compte AD » apparaît, à faire avant la fin du créneau. |
| 9 | technicien@ | « Désactiver le compte AD », puis **C'est fait**. | Intervention « Refermé ». Le compte redevient dormant. |
| 10 | dsi@ | Ouvrez l'habilitation et demandez une ouverture. | La demande est validée d'office : une tâche d'activation part directement chez le référent technique. |
| 11 | rssi@ ou dsi@ | Activez l'accès (étape 8), puis **Révoquer l'habilitation** avec un motif. | Habilitation « Révoquée ». La désactivation devient urgente chez le référent technique. |
| 12 | rssi@ | **Journal d'audit**. | Toutes les actions sont tracées, avec le bandeau « Chaîne d'intégrité vérifiée ». |

Le compte de démonstration `thomas.girard@demo.invalid` existe déjà : il permet de commencer directement à l'étape 3, après qu'un référent lui a créé une habilitation (étape 1 avec son email).

## 4. Contrôles de sécurité à essayer

- Se connecter en prestataire sans saisir le code MFA : toutes les pages renvoient vers la vérification.
- Ouvrir un lien d'invitation une deuxième fois : « Lien invalide ou expiré ».
- En référent technique, ouvrir l'adresse `/audit/` : accès refusé (403).
- En administration (`/admin/`, avec un compte créé par `createsuperuser`), publier une version 2.0 de la charte : l'intervenant ne peut plus demander d'intervention tant qu'il ne l'a pas signée.
- Vérifier l'intégrité du journal en ligne de commande : `python manage.py verifier_audit`.

## 5. Tests automatisés

```bash
python manage.py test tests
```

Résultat attendu : 42 tests réussis.
