# Portail prestataires

Portail web de l'établissement pour sécuriser les accès des prestataires : signature de la charte, habilitations, demandes d'intervention et ouverture des accès à la demande, avec un journal d'audit infalsifiable.

Principe : **aucun accès sans charte signée, validation et date de fin**. Le compte d'un prestataire reste désactivé et ne s'ouvre que le temps d'une intervention validée.

## État d'avancement

| Lot | Contenu | État |
| --- | --- | --- |
| 1. Socle et charte | Comptes, SSO Entra ID pour le personnel, MFA TOTP obligatoire pour les prestataires, sociétés et intervenants, invitations, versions de charte, signature simple intégrée, journal d'audit chaîné | Fait |
| 2. Demandes et validations | Habilitations (validation RSSI, création BeyondTrust par le référent technique), demandes d'intervention (validation par le référent applicatif, d'office pour lui-même ou la DSI), tâches d'ouverture et de fermeture du compte AD, révocation | En cours |
| 3. Automatisation | Activation et désactivation automatiques du compte AD (VPN Check Point et BeyondTrust suivent), expirations, rappels, revues | À venir |
| 4. Extensions | Applications métier hors AD, badges Horoquartz, export SIEM | À venir |

## Rôles

Le personnel se connecte avec son compte de l'établissement (Entra ID). Ses rôles dans le portail sont recalculés à chaque connexion depuis ses groupes AD (variable `OIDC_GROUPES_ROLES`) :

- RSSI
- DSI
- Référent interne
- Référent applicatif
- Référent technique

Les prestataires ont un compte local au portail : mot de passe de 12 caractères minimum et application d'authentification (TOTP) obligatoire. Ils ne peuvent pas utiliser le SSO.

## Sécurité

- **MFA** : TOTP obligatoire pour les prestataires et pour tout compte local, y compris l'administration Django. Le personnel est soumis à la MFA d'Entra ID (accès conditionnel).
- **Signature de la charte** : lecture complète obligatoire, case d'engagement, code MFA vérifié au moment de signer. Le portail conserve l'horodatage, l'adresse IP, le navigateur, l'empreinte SHA-256 du texte signé et une empreinte de preuve. Une version publiée ne peut plus être modifiée, et chaque nouvelle version doit être re-signée.
- **Journal d'audit** : ajout seul. Chaque entrée est chaînée à la précédente par empreinte SHA-256. Sous PostgreSQL, un trigger interdit UPDATE, DELETE et TRUNCATE. La commande `python manage.py verifier_audit` contrôle l'intégrité de la chaîne, qui est aussi vérifiée à chaque affichage du journal.
- **Web** : HTTPS imposé, HSTS, cookies `__Host-` sécurisés, CSP stricte sans script ni style en ligne, protection contre l'intégration en iframe, session expirant après 30 minutes d'inactivité.
- **Adresse IP** : l'en-tête `X-Forwarded-For` n'est pris en compte que s'il vient d'un reverse proxy déclaré dans `PORTAIL_PROXIES_DE_CONFIANCE`.

## Démarrer en local

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
export PORTAIL_DEBUG=1
python manage.py migrate
python manage.py charger_demo          # société, intervenant, charte, application et comptes de démonstration
python manage.py createsuperuser       # compte d'administration (TOTP demandé à la connexion)
python manage.py runserver
```

Ouvrez http://127.0.0.1:8000. Le compte de démonstration est `thomas.girard@demo.invalid`, avec le mot de passe `Demo-prestataire-2026`. Le portail vous demande alors d'enregistrer une application d'authentification.

Pour lancer les tests : `python manage.py test tests`. Parcours de recette pas à pas : [docs/guide-de-test.md](docs/guide-de-test.md).

## Déployer sur un serveur interne

1. Copiez `.env.example` en `.env` et complétez-le : clé secrète, nom d'hôte, mot de passe PostgreSQL, Entra ID, SMTP.
2. Lancez `docker compose up -d --build`. Le portail écoute sur `127.0.0.1:8000`.
3. Placez le reverse proxy TLS de l'établissement devant ce port. Déclarez son adresse dans `PORTAIL_PROXIES_DE_CONFIANCE`, et faites-lui transmettre `X-Forwarded-Proto: https`.
4. Créez le compte d'administration : `docker compose exec web python manage.py createsuperuser`.

### Enregistrer l'application dans Entra ID

- URI de redirection : `https://<hôte>/oidc/callback/`
- Revendication facultative `groups` (identifiants des groupes de sécurité) dans le jeton d'identité
- Renseigner `ENTRA_TENANT_ID`, `OIDC_RP_CLIENT_ID`, `OIDC_RP_CLIENT_SECRET` et `OIDC_GROUPES_ROLES`

## Organisation du code

| Dossier | Rôle |
| --- | --- |
| `portail/` | Configuration, URLs, en-têtes de sécurité |
| `comptes/` | Utilisateurs, SSO Entra ID, rôles, MFA, invitations |
| `prestataires/` | Sociétés et intervenants |
| `charte/` | Versions de charte et signatures |
| `acces/` | Applications, habilitations, interventions, tâches techniques ; règles de workflow dans `acces/workflow.py` |
| `audit/` | Journal d'audit chaîné |
| `tests/` | Tests automatisés |
