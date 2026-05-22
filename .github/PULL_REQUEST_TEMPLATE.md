## Résumé

<!-- 1-2 phrases sur le quoi et le pourquoi. -->

## Type

- [ ] feat - [ ] fix - [ ] chore - [ ] docs - [ ] refactor - [ ] test - [ ] perf - [ ] build - [ ] ci

## Changements

-

## Checklist générale

- [ ] Titre PR au format Conventional Commits (`feat(scope): ...`)
- [ ] Pas de secret en clair (utiliser SOPS+age)
- [ ] CI verte (lint + tests + security scan)
- [ ] Doc mise à jour si nécessaire (README, ADR, CHANGELOG)

## Checklist Terraform (si applicable)

- [ ] `tofu fmt -recursive` passé
- [ ] `tofu validate` OK
- [ ] `tflint` 0 warning
- [ ] Plan inspecté + commenté dans la PR

## Checklist Ansible (si applicable)

- [ ] `ansible-lint --offline` propre
- [ ] Idempotent (2e run = 0 changed)
- [ ] Molecule test passe (si rôle critique)

## Checklist sécurité (si applicable)

- [ ] Pas de password / token en clair
- [ ] OPA Conftest passe (`conftest test`)
- [ ] gitleaks pre-commit hook propre

Refs #

