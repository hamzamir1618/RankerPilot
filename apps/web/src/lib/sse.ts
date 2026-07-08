"use client"

import { useEffect, useState } from "react"
import { getAccessToken } from "./api-client"

export type AuditEvent = {
  type: string
  audit_id: string
  agent?: string
  findings_count?: number
  elapsed_ms?: number
  [key: string]: unknown
}

export function useAuditEvents(auditId: string) {
  const [events, setEvents] = useState<AuditEvent[]>([])
  const [status, setStatus] = useState<"connecting" | "connected" | "disconnected">("connecting")

  useEffect(() => {
    if (!auditId) return

    let eventSource: EventSource | null = null
    let reconnectTimeout: NodeJS.Timeout

    const connect = () => {
      setStatus("connecting")
      const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
      const token = getAccessToken()
      
      // Pass token in URL for EventSource since EventSource doesn't support custom headers easily
      // Alternatively, the backend accepts it in cookies
      eventSource = new EventSource(`${baseUrl}/v1/audits/${auditId}/events?token=${token || ""}`)
      
      eventSource.onopen = () => {
        setStatus("connected")
      }
      
      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as AuditEvent
          setEvents(prev => [...prev, data])
        } catch (e) {
          console.error("Failed to parse SSE message", e)
        }
      }
      
      eventSource.onerror = (error) => {
        console.error("SSE connection error", error)
        setStatus("disconnected")
        eventSource?.close()
        // Reconnect after 3 seconds
        reconnectTimeout = setTimeout(connect, 3000)
      }
    }

    connect()

    return () => {
      if (eventSource) {
        eventSource.close()
      }
      clearTimeout(reconnectTimeout)
    }
  }, [auditId])

  // Get the most recent event to determine current status message
  const latestEvent = events[events.length - 1]
  
  let progressMessage = ""
  if (latestEvent) {
    if (latestEvent.type === "crawl.progress") {
      progressMessage = `Crawling... ${latestEvent.crawled}/${latestEvent.total || '?'} pages`
    } else if (latestEvent.type === "agent.started") {
      progressMessage = `Running ${latestEvent.agent} agent...`
    } else if (latestEvent.type === "agent.completed") {
      progressMessage = `Completed ${latestEvent.agent} agent in ${latestEvent.elapsed_ms}ms`
    } else if (latestEvent.type === "score.computed") {
      progressMessage = `Computing final score...`
    } else if (latestEvent.type === "audit.done") {
      progressMessage = `Done!`
    }
  }

  return { events, status, progressMessage, latestEvent }
}
