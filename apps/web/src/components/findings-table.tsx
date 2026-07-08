"use client"

import React, { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { apiClient } from "@/lib/api-client"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { ChevronDown, ChevronRight, AlertCircle, AlertTriangle, CheckCircle } from "lucide-react"

export function FindingsTable({ auditId }: { auditId: string }) {
  const [cursor, setCursor] = useState<string | null>(null)
  const [severityFilter, setSeverityFilter] = useState<string>("")
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set())

  // Note: For a real infinite scroll or robust pagination, useInfiniteQuery is better.
  // Here we use simple cursor pagination with load more / next page logic.
  const { data, isLoading } = useQuery({
    queryKey: ["findings", auditId, severityFilter, cursor],
    queryFn: async () => {
      const { data, error } = await apiClient.GET("/v1/audits/{audit_id}/findings", {
        params: { 
          path: { audit_id: auditId },
          query: { 
            severity: severityFilter || undefined,
            cursor: cursor || undefined,
            limit: 10
          }
        }
      })
      if (error) throw new Error("Failed to load findings")
      return data
    }
  })

  const toggleRow = (id: string) => {
    const newExpanded = new Set(expandedRows)
    if (newExpanded.has(id)) newExpanded.delete(id)
    else newExpanded.add(id)
    setExpandedRows(newExpanded)
  }

  const getSeverityIcon = (severity: string | null) => {
    switch (severity) {
      case "high": return <AlertCircle className="w-4 h-4 text-red-500" />
      case "medium": return <AlertTriangle className="w-4 h-4 text-orange-500" />
      case "low": return <AlertTriangle className="w-4 h-4 text-yellow-500" />
      default: return <CheckCircle className="w-4 h-4 text-green-500" />
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex gap-2 mb-4">
        <select 
          className="border rounded p-2 bg-white"
          value={severityFilter} 
          onChange={e => { setSeverityFilter(e.target.value); setCursor(null) }}
        >
          <option value="">All Severities</option>
          <option value="high">High</option>
          <option value="medium">Medium</option>
          <option value="low">Low</option>
        </select>
      </div>

      <div className="border rounded-md">
        <Table>
          <TableHeader className="bg-slate-50">
            <TableRow>
              <TableHead className="w-[50px]"></TableHead>
              <TableHead>Title</TableHead>
              <TableHead>Category</TableHead>
              <TableHead>Severity</TableHead>
              <TableHead>Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              <TableRow><TableCell colSpan={5} className="text-center py-4">Loading findings...</TableCell></TableRow>
            ) : data?.length === 0 ? (
              <TableRow><TableCell colSpan={5} className="text-center py-4 text-slate-500">No findings match your criteria.</TableCell></TableRow>
            ) : (
              data?.map((finding: Record<string, unknown>) => (
                <React.Fragment key={finding.id as string}>
                  <TableRow className="cursor-pointer hover:bg-slate-50" onClick={() => toggleRow(finding.id as string)}>
                    <TableCell>
                      {expandedRows.has(finding.id) ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                    </TableCell>
                    <TableCell className="font-medium">{finding.title as string}</TableCell>
                    <TableCell><Badge variant="outline" className="capitalize">{finding.category as string}</Badge></TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2 capitalize">
                        {getSeverityIcon(finding.severity as string | null)}
                        {(finding.severity as string) || "None"}
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant={finding.status === "pass" ? "secondary" : "destructive"}>
                        {finding.status as string}
                      </Badge>
                    </TableCell>
                  </TableRow>
                  
                  {expandedRows.has(finding.id as string) && (
                    <TableRow className="bg-slate-50/50">
                      <TableCell colSpan={5} className="p-0">
                        <div className="p-6 grid grid-cols-1 md:grid-cols-2 gap-6 border-b border-slate-100">
                          <div>
                            <h4 className="text-sm font-semibold text-slate-700 mb-2">Evidence</h4>
                            <pre className="bg-slate-900 text-slate-100 p-4 rounded-lg text-sm overflow-auto">
                              {JSON.stringify(finding.evidence, null, 2)}
                            </pre>
                          </div>
                          <div className="space-y-4">
                            {finding.fix && (
                              <div>
                                <h4 className="text-sm font-semibold text-slate-700 mb-2">How to Fix</h4>
                                <p className="text-sm text-slate-600">{finding.fix as string}</p>
                              </div>
                            )}
                            {finding.fix_code && (
                              <div>
                                <h4 className="text-sm font-semibold text-slate-700 mb-2">Example Code</h4>
                                <pre className="bg-slate-800 text-green-400 p-4 rounded-lg text-sm overflow-auto">
                                  {finding.fix_code as string}
                                </pre>
                              </div>
                            )}
                          </div>
                        </div>
                      </TableCell>
                    </TableRow>
                  )}
                </React.Fragment>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      <div className="flex justify-between items-center mt-4">
        <Button 
          variant="outline" 
          disabled={!data?.next_cursor}
          onClick={() => setCursor(data?.next_cursor || null)}
        >
          Load More / Next
        </Button>
      </div>
    </div>
  )
}
