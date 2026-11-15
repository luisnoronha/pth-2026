# frontend

Static pages, no build step.

| Folder | Pages |
|---|---|
| `demo_pages/` | the fictional Acme Corp site Rex is asked to brief: `acme-ir.html` (hidden note caught by the sanitiser), `acme-ir-v2.html` (same note, three words changed), `acme-q3.html` (clean fact sheet) |
| `board/` | the attacker's webhook board: quiet until a secret arrives, then red. Polls the webhook's `/hits` |
| `web/` | Hack Rex: `index.html` (attack page, built for phones), `scoreboard.html` (big screen), `admin.html` (host's control panel) |

The pages read `config.js` for the API and webhook URLs: written by Terraform on AWS, served empty by `hackrex-local` (same origin).
