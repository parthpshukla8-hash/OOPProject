import { createContext, useContext } from 'react'

export type NoticeIntent = 'success' | 'error' | 'info'
export const NotifyContext = createContext<(intent: NoticeIntent, message: string) => void>(() => undefined)
export const useNotify = () => useContext(NotifyContext)
