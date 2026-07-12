// A work item is terminal when its outcome is set (finished/failed/cancelled),
// derived server-side from the subject's runs + the merge event.
//
// The old build-dashboard reducers (mergeDashboardItem / dropDashboardItem /
// mergeHealth / mergePending + the code/scope bucketing) lived here too; they
// were retired with the dashboard itself — the active board (WorkItemsPage)
// and history (HistoryPage) replaced it, so only this predicate remains.
export function isTerminal(outcome: string | null | undefined): boolean {
  return outcome != null
}
