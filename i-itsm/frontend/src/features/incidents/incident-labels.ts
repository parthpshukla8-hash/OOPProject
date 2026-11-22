import type { IncidentPriority, IncidentStatus, IncidentSummary, UserRole } from '../../api/types'

export const PRIORITY_LABEL: Record<IncidentPriority, string> = {
  P1: 'Critical', P2: 'High', P3: 'Medium', P4: 'Low',
}

export const STATUS_LABEL: Record<IncidentStatus, string> = {
  NEW: 'New',
  CLASSIFIED: 'Waiting for a technician',
  ASSIGNED: 'Assigned',
  ACKNOWLEDGED: 'Acknowledged',
  IN_PROGRESS: 'Being investigated',
  WAITING_FOR_INFO: 'Waiting for your reply',
  RESOLVED: 'Resolved',
  VERIFIED: 'Confirmed fixed',
  CLOSED: 'Closed',
}

/** What the status means for the person looking at it. */
export function describeStatus(incident: Pick<IncidentSummary, 'status' | 'assignee'>, role: UserRole): string {
  const name = incident.assignee?.displayName
  if (role === 'EMPLOYEE') {
    switch (incident.status) {
      case 'ASSIGNED': return name ? `${name} has been notified` : 'A technician has been notified'
      case 'ACKNOWLEDGED': return name ? `${name} has picked it up` : 'A technician has picked it up'
      case 'IN_PROGRESS': return name ? `${name} is working on it` : 'Being investigated'
      case 'WAITING_FOR_INFO': return 'Waiting for your reply'
      case 'RESOLVED': return 'Fixed. Please confirm it works'
      default: return STATUS_LABEL[incident.status]
    }
  }
  if (incident.status === 'WAITING_FOR_INFO') return 'Waiting for the reporter'
  if (incident.status === 'CLASSIFIED') return 'Unassigned'
  return STATUS_LABEL[incident.status]
}

export const FINISHED: IncidentStatus[] = ['RESOLVED', 'VERIFIED', 'CLOSED']

export const AUDIT_ACTION_LABEL: Record<string, string> = {
  IncidentReported: 'Reported', IncidentClassified: 'Classified', TechnicianAssigned: 'Assigned',
  IncidentAcknowledged: 'Acknowledged', InvestigationStarted: 'Investigation started',
  InformationRequested: 'Information requested', InformationProvided: 'Information provided',
  IncidentResolved: 'Resolved', IncidentVerified: 'Verified', IncidentReopened: 'Reopened',
  IncidentClosed: 'Closed', PriorityChanged: 'Priority changed', IncidentUpdated: 'Updated',
  SlaWarningRaised: 'SLA warning', SlaViolated: 'SLA breached', IncidentEscalated: 'Escalated',
  DuplicateFlagged: 'Possible duplicate', RootCauseIdentified: 'Probable cause found',
  IncidentJoined: 'Another person affected', NoteAdded: 'Note added', FeedbackSubmitted: 'Feedback',
  AssignmentPending: 'Assignment pending',
}
