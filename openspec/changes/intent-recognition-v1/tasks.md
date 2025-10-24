# Tasks: intent-recognition-v1

1. Scaffold change dir (proposal/tasks/design/specs) based on prd/intent/*.md
2. Draft common specs: evidence-policy / map-layers / uav-track-simulation / java-api-contract-todo (with JSON examples)
3. Draft per-capability specs: intent-routing / report-intake / annotation-lifecycle / route-safe-point / device-status / robotdog-control / recon-minimal / plan-task-approval / rfa-request / event-update / video-analyze-report-mode / rescue-task-generate / evidence-bookmark-playback
4. Add at least 1 Scenario per spec (inputs/actions/expected/acceptance)
5. Cross-reference: evidence-policy → rescue/approval gate; map-layers → recon/annotations/routes consumers
6. Validate with `openspec validate intent-recognition-v1 --strict` and resolve warnings
7. Review with stakeholders; finalize KPIs and sign-off
