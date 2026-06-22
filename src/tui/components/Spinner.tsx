import React, { useEffect, useState } from 'react'
import { Text } from 'ink'

const frames = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']

/**
 * 简单的 spinner 动画组件。
 * 50ms 帧间隔。
 */
export function Spinner() {
  const [frame, setFrame] = useState(0)

  useEffect(() => {
    const timer = setInterval(() => {
      setFrame(prev => (prev + 1) % frames.length)
    }, 50)
    return () => clearInterval(timer)
  }, [])

  return <Text>{frames[frame]} </Text>
}
