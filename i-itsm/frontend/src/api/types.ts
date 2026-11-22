export type UserRole = 'EMPLOYEE' | 'TECHNICIAN' | 'ADMINISTRATOR'
export type IncidentStatus =
  | 'NEW' | 'CLASSIFIED' | 'ASSIGNED' | 'ACKNOWLEDGED' | 'IN_PROGRESS'
  | 'WAITING_FOR_INFO' | 'RESOLVED' | 'VERIFIED' | 'CLOSED'
export type IncidentPriority = 'P1' | 'P2' | 'P3' | 'P4'
export type SlaState = 'on_track' | 'at_risk' | 'breached' | 'met'

export interface Person { id: number; displayName: string; role: UserRole }

export interface CurrentUser {
  id: number; username: string; firstName: string; lastName: string; displayName: string
  email: string; phone: string; role: UserRole; isActive: boolean; isAvailable: boolean
  experienceYears: number; maxActiveIncidents: number; skillIds: number[]
  teamLead: number | null; isItManager: boolean; activeIncidentCount: number
}

export interface SlaSnapshot {
  status: SlaState; responseProgress: number; resolutionProgress: number; minutesToResolutionDue: number | null
}

export interface IncidentSummary {
  id: number; code: string; title: string; status: IncidentStatus; priority: IncidentPriority
  reporter: Person; assignee: Person | null
  service: number | null; serviceName: string | null; category: number | null; categoryName: string | null
  affectedUsers: number; createdAt: string; updatedAt: string
  responseDueAt: string | null; resolutionDueAt: string | null
  escalationLevel: number; sla: SlaSnapshot; searchScore: number | null
}

export interface IncidentComment {
  id: number; author: Person; kind: 'NOTE' | 'INFO_REQUEST' | 'INFO_REPLY' | 'JOINED'
  body: string; isInternal: boolean; createdAt: string
}

export interface IncidentAction {
  key: string; label: string; needs: string | null; needsLabel: string; primary: boolean
}

export interface IncidentDetail extends IncidentSummary {
  description: string; impact: number; urgency: number; priorityScore: number; priorityRationale: string[]
  resolution: string; acknowledgedAt: string | null; resolvedAt: string | null
  verifiedAt: string | null; closedAt: string | null; reopenCount: number
  feedbackRating: number | null; feedbackComment: string
  comments: IncidentComment[]; availableActions: IncidentAction[]
  prediction: { probability: number; expectedMinutes: number | null; minutesLeft: number | null } | null
  duplicateOf: number | null; duplicateOfCode: string | null
  probableRootCauseDetail: { id: number; code: string; title: string; service: string } | null
  escalationLabel: string; alsoAffectedCount: number
}

export interface AuditEvent {
  id: number; incident: number | null; incidentCode: string | null; actor: Person | null
  action: string; previousState: string; newState: string; description: string; createdAt: string
}

export interface NotificationItem {
  id: number; incident: number | null; incidentCode: string | null
  channel: 'IN_APP' | 'EMAIL' | 'SMS'; recipientName: string; subject: string; body: string; isRead: boolean; createdAt: string
}

export interface Category { id: number; name: string; description: string; keywords: string }
export interface Service {
  id: number; name: string; description: string; keywords: string
  businessCriticality: number; defaultCategory: number | null; isActive: boolean
}
export interface ServiceDependency { id: number; service: number; dependsOn: number }
export interface SlaPolicy {
  id: number; priority: IncidentPriority; service: number | null; responseMinutes: number; resolutionMinutes: number
}

export interface LabelSuggestion { id: number; name: string; score: number; matchedTerms: string[] }
export interface SimilarIncident {
  id: number; code: string; title: string; status: IncidentStatus; priority?: IncidentPriority
  service?: string | null; score: number; level: 'likely_duplicate' | 'related'; matchedTerms: string[]
  reportedByMe?: boolean; alreadyJoined?: boolean; createdAt?: string
}
export interface ResolutionSuggestion {
  incidentCode: string; incidentId: number; title: string; resolution: string
  score: number; matchedTerms: string[]; solvedBy: string | null
}
export interface ReportAnalysis {
  categories: LabelSuggestion[]; services: LabelSuggestion[]
  similar: SimilarIncident[]; resolutions: ResolutionSuggestion[]
  priority: { priority: IncidentPriority; score: number; rationale: string[] } | null
}
export interface TechnicianRecommendation {
  technician: { id: number; displayName: string }; score: number; reasons: string[]
}
export interface IncidentInsights {
  similar: SimilarIncident[]; resolutions: ResolutionSuggestion[]; recommendations: TechnicianRecommendation[]
}

export interface TechnicianWorkload {
  id: number; name: string; username: string; active: number; capacity: number
  resolved: number; isAvailable: boolean; skills: string[]
}
export interface PredictedBreach {
  incidentId: number; code: string; title: string; priority: IncidentPriority
  probability: number; expectedMinutes: number | null; minutesLeft: number | null
}
export interface IncidentCluster {
  incidentIds: number[]; incidentCodes: string[]; titles: string[]; size: number
  services: string[]; topTerms: string[]; highestPriority: IncidentPriority
}
export interface Overview {
  total: number; open: number; criticalOpen: number; resolved: number; slaViolations: number
  averageResolutionMinutes: number | null
  averageResolutionByPriority: Record<IncidentPriority, number | null>
  byPriority: Record<IncidentPriority, number>; byStatus: Record<string, number>
  byService: { name: string | null; count: number }[]; byCategory: { name: string | null; count: number }[]
  feedback: { average: number | null; count: number }
  dailyVolume: { date: string; count: number }[]
}
export interface FullReport extends Overview {
  technicianWorkload: TechnicianWorkload[]; correlations: IncidentCluster[]; predictedBreaches: PredictedBreach[]
}
export interface AttentionItem {
  incidentId: number; code: string; title: string; priority: IncidentPriority
  reasons: string[]; assignee: string | null; minutesToResolutionDue: number | null
}
export interface Situation {
  attention: AttentionItem[]; predictedBreaches: PredictedBreach[]
  correlations: IncidentCluster[]; overview: Overview
}
export interface ServiceMapNode {
  id: number; name: string; businessCriticality: number; openIncidents: number
  worstPriority: IncidentPriority | null; health: 'healthy' | 'degraded' | 'down'
  reliesOn: number[]; affects: number[]
}
export interface ServiceMapData { nodes: ServiceMapNode[]; edges: { service: number; dependsOn: number }[] }

export interface StrategyOption { key: string; label: string; description: string }
export interface SystemSettings {
  assignmentStrategy: string; priorityStrategy: string
  options: { assignment: StrategyOption[]; priority: StrategyOption[] }
}
