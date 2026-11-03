"use client"

import { useEffect, useRef } from "react"

import { incrementViewsAction } from "@/app/actions"

/** Counts a view once per visit; done client-side so prefetches don't inflate it. */
export function ViewCounter({ postId }: { postId: number }) {
  const counted = useRef<number | null>(null)

  useEffect(() => {
    if (counted.current === postId) return
    counted.current = postId
    void incrementViewsAction(postId)
  }, [postId])

  return null
}
