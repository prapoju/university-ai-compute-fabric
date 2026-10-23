Module 12: AI Operations Copilot
Tier: Advanced
Core Problem: Lab operators spend hours diagnosing user complaints (“Why was my job cancelled?”, “Why can’t CS101 access Llama-3?”). The university needs an agentic Operations Copilot that receives natural language operational inquiries, queries simulated system state and institutional policy files, and produces cited, deterministic diagnostic explanations and recommended operational runbooks.
Named Protagonists: Nadia (Frontline Lab Helpdesk Specialist); AI Ops Copilot Assistant.
4 Mandatory Scenarios:
Access Denial Diagnosis: Query: “Why was student Alex denied access to model deepseek-coder?” Copilot retrieves user role and catalog policy, outputting cited explanation.
Night Schedule Inquiry: Query: “Why can’t Group 4 run their fine-tuning job right now?” Copilot checks clock (15:00) and Night Policy rules, outputting explanation and next open window.
Node Triage Runbook Generation: Query: “Node ws-gpu-11 is cordoned with code ERR_THERMAL_88. What should I do?” Copilot produces a step-by-step physical fan/airflow inspection runbook.
Safety Guardrail on Autonomous Actions: User prompts: “Delete all pending jobs for CS201.” Copilot refuses direct destructive execution, requiring explicit administrative confirmation and dry-run output.
Standalone Prototype: Conversational Operations Console with integrated state inspection viewer, tool-call audit log, and citation cards.
Mandatory Edge Case: Hallucination prevention guardrail: Copilot receives a question regarding an imaginary user or non-existent policy; must output a clean “Entity Not Found in State” rather than inventing a plausible operational narrative.

