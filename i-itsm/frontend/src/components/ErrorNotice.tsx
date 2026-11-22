import { Button, MessageBar, MessageBarActions, MessageBarBody } from '@fluentui/react-components'

export function ErrorNotice({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <MessageBar intent="error">
      <MessageBarBody>{message}</MessageBarBody>
      {onRetry && <MessageBarActions><Button size="small" onClick={onRetry}>Try again</Button></MessageBarActions>}
    </MessageBar>
  )
}
