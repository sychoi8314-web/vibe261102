import Link from "next/link"
import { PenLineIcon, MessagesSquareIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { ThemeToggle } from "@/components/theme-toggle"

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-40 border-b bg-background/80 backdrop-blur">
      <div className="mx-auto flex h-14 w-full max-w-4xl items-center gap-2 px-4">
        <Link href="/" className="flex items-center gap-2 font-semibold">
          <MessagesSquareIcon className="size-5" />
          DemoWeb 게시판
        </Link>
        <div className="ml-auto flex items-center gap-1">
          <Button
            size="sm"
            nativeButton={false}
            render={<Link href="/posts/new" />}
          >
            <PenLineIcon data-icon="inline-start" />
            글쓰기
          </Button>
          <ThemeToggle />
        </div>
      </div>
    </header>
  )
}
