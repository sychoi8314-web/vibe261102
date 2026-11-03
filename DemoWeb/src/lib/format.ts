const TIME_ZONE = "Asia/Seoul"

const dateFormat = new Intl.DateTimeFormat("ko-KR", {
  timeZone: TIME_ZONE,
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
})

const timeFormat = new Intl.DateTimeFormat("ko-KR", {
  timeZone: TIME_ZONE,
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
})

/** Board-list style: time for today's posts, date otherwise. */
export function formatShort(iso: string, now: Date) {
  const date = new Date(iso)
  return dateFormat.format(date) === dateFormat.format(now)
    ? timeFormat.format(date)
    : dateFormat.format(date)
}

export function formatFull(iso: string) {
  const date = new Date(iso)
  return `${dateFormat.format(date)} ${timeFormat.format(date)}`
}
