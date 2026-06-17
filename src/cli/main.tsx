import React from 'react'
import { render } from 'ink'
import { App } from '../tui/App.js'

const args = process.argv.slice(2)
const cwd = process.env.GENERAL_AGENT_CALLER_DIR ?? process.cwd()

render(<App args={args} cwd={cwd} />)
