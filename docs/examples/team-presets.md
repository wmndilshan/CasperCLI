# Team Presets

## Presets

- `solo`
  - single generalist worker with governance agents
  - best for small refactors and repo-wide maintenance
- `fullstack`
  - planner, backend, frontend, QA
  - best for application features that span API and UI
- `backend-platform`
  - planner, backend-heavy workers, QA, devops
  - best for runtime, API, storage, jobs, and platform work
- `frontend-experience`
  - planner, frontend-heavy workers, QA
  - best for UX-heavy application changes
- `ai-ml`
  - planner, ML, backend, QA
  - best for RAG, evaluation, model serving, and data pipelines
- `devops`
  - planner, devops, backend, QA
  - best for CI/CD, infra, containers, and observability
- `incident-response`
  - planner, backend, QA, security
  - best for hotfixes, rollback, containment, and verification
- `enterprise-strict`
  - full governance with stricter review and ownership modes
  - best for high-control repositories
- `startup-mvp`
  - lighter gates and faster generalist delivery
  - best for speed-biased product work

## Example Invocations

```bash
python main.py run "stabilize the billing API and background jobs" --team backend-platform --team-size 5 --verify strict
python main.py run "refresh onboarding UX and add regression tests" --team frontend-experience --team-size 4
python main.py run "contain auth outage and patch audit gaps" --team incident-response --strict --verify strict
python main.py inspect-team --goal "prepare a RAG API with evaluation dashboards" --team ai-ml --team-size 5
```
