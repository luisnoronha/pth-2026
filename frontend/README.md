# frontend

Static pages, no build step.

- `demo_pages/`: the poisoned pages for Demo 1 (`acme-ir.html` v1, `acme-ir-v2.html` paraphrased)
- `board/`: the big-screen webhook board for Demo 1 (`index.html`, polls the webhook Lambda's `/hits`)
- `web/`: Hack Rex `index.html` (attack page, mobile), `scoreboard.html` (big screen), `admin.html` (speaker). Served locally by `hackrex-local` (see `strands/README.md`)

See [docs/03-demos.md](../docs/03-demos.md).

The pages read `config.js` (API and webhook URLs): written by Terraform on AWS, served empty by `hackrex-local`.
