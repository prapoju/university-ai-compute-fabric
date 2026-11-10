// The rule id a policy clause prints next to itself in its evidence snippet. Mirrors src/domain/rule_ids.py
// (story 1.6, rule_of_clause): the parenthesised RULE-XXX-NN right after the clause id. The console shows the
// badge from this fixed pattern; it holds no rule logic. The E2E pins the exact badge text.
const RULE_CODE = 'RULE-[A-Z]+-\\d{2}';

export function ruleOfClause(snippet: string, clauseId: string): string | null {
  const escaped = clauseId.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const match = new RegExp(`${escaped} \\((${RULE_CODE})\\)`).exec(snippet);
  return match?.[1] ?? null;
}
