import { registerExtensionUI } from '../registry'
import { BUILD } from './api'
import { parseLeadingId } from './slug'
import { AgentCallPage } from './AgentCallPage'
import { HistoryPage } from './HistoryPage'
import { NotFound } from './NotFound'
import { ProjectsPage } from './projects/ProjectsPage'
import { WorkItemPage } from './WorkItemPage'
import { WorkItemsPage } from './WorkItemsPage'

// build contributes its UI through the same registry any extension uses — its pages
// are not the app's spine, they're one extension's routes. The shell mounts these and
// derives build's subnav from ``nav``; feed, settings, and usage it gets for free.
registerExtensionUI({
  name: BUILD,
  home: `/${BUILD}`,
  systemStrip: true,
  nav: [
    { href: `/${BUILD}`, label: 'active', match: (loc) => loc === `/${BUILD}` || isWorkItem(loc) },
    { href: `/${BUILD}/history`, label: 'history' },
    { href: `/${BUILD}/projects`, label: 'projects' },
  ],
  routes: [
    { path: `/${BUILD}`, render: () => <WorkItemsPage /> },
    { path: `/${BUILD}/history`, render: () => <HistoryPage /> },
    { path: `/${BUILD}/projects`, render: () => <ProjectsPage /> },
    {
      path: '/work-items/:slug/agent-calls/:callId',
      render: ({ slug, callId }) => {
        const workItemId = slug ? parseLeadingId(slug) : Number.NaN
        if (!Number.isFinite(workItemId) || !callId) return <NotFound />
        return <AgentCallPage workItemId={workItemId} runId={callId} />
      },
    },
    {
      path: '/work-items/:slug',
      render: ({ slug }) => {
        const id = slug ? parseLeadingId(slug) : Number.NaN
        if (!Number.isFinite(id)) return <NotFound />
        return <WorkItemPage workItemId={id} />
      },
    },
  ],
})

// A work-item detail URL (item page or its agent-call child). build's detail pages
// live off ``/work-items``, so its "active" tab lights on them too.
function isWorkItem(location: string): boolean {
  return location.startsWith('/work-items/')
}
