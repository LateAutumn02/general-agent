import React from 'react'
import { Box, Text } from 'ink'
import { theme } from '../theme.js'
import type { PermissionRequest } from '../types.js'

type PermissionPromptProps = {
  request: PermissionRequest
  denyReason: string
  collectingDenyReason: boolean
}

export function PermissionPrompt({
  request,
  denyReason,
  collectingDenyReason,
}: PermissionPromptProps) {
  return (
    <Box flexDirection="column" paddingX={1} paddingY={1}>
      <Text backgroundColor={theme.inputBackground} color="white">
        * Running {request.toolName}
      </Text>
      <Text backgroundColor={theme.inputBackground} color="white">
        Would you like to run the following command?
      </Text>
      <Text backgroundColor={theme.inputBackground} color={theme.muted}>
        Reason: {request.reason}
      </Text>
      <Text backgroundColor={theme.inputBackground} color="white">
        $ {request.command}
      </Text>
      <Text backgroundColor={theme.inputBackground} color={theme.inputText}>
        1. Yes, proceed (y)
      </Text>
      <Text backgroundColor={theme.inputBackground} color={theme.inputText}>
        2. Yes, and don't ask again for commands that start with `{request.prefixRule}` (p)
      </Text>
      <Text backgroundColor={theme.inputBackground} color={theme.inputText}>
        3. No, and tell general-agent what to do differently (n)
      </Text>
      {collectingDenyReason ? (
        <Text backgroundColor={theme.inputBackground} color={theme.inputText}>
          No reason: {denyReason || 'type a note and press Enter'}
        </Text>
      ) : null}
    </Box>
  )
}
