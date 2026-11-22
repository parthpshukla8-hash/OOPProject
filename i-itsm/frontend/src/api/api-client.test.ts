import { describe, expect, it } from 'vitest'
import { camelizeKeys, snakeizeKeys } from './api-client'

describe('api key translation', () => {
  it('turns snake_case response keys into camelCase', () => {
    expect(camelizeKeys({ response_due_at: 1, nested: [{ matched_terms: ['a'] }] }))
      .toEqual({ responseDueAt: 1, nested: [{ matchedTerms: ['a'] }] })
  })

  it('leaves status and priority codes untouched', () => {
    expect(camelizeKeys({ by_status: { IN_PROGRESS: 2, WAITING_FOR_INFO: 1 }, by_priority: { P1: 3 } }))
      .toEqual({ byStatus: { IN_PROGRESS: 2, WAITING_FOR_INFO: 1 }, byPriority: { P1: 3 } })
  })

  it('turns camelCase request keys into snake_case', () => {
    expect(snakeizeKeys({ affectedUsers: 3, skillIds: [1] })).toEqual({ affected_users: 3, skill_ids: [1] })
  })
})
