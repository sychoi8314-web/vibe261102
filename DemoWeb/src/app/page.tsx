import { Suspense } from "react"
import Link from "next/link"
import Form from "next/form"
import { MessageSquareIcon, SearchIcon } from "lucide-react"

import { CATEGORIES, isCategory, listPosts, type Category } from "@/lib/board"
import { formatShort } from "@/lib/format"
import { cn } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { BoardPagination } from "@/components/board-pagination"

type SearchParams = Awaited<PageProps<"/">["searchParams"]>

function first(value: string | string[] | undefined) {
  return Array.isArray(value) ? value[0] : value
}

function parseParams(params: SearchParams) {
  const category = first(params.category)
  return {
    category: isCategory(category) ? category : undefined,
    query: first(params.q)?.trim() || undefined,
    page: Number(first(params.page)) || 1,
  }
}

function boardHref(params: {
  category?: Category
  query?: string
  page?: number
}) {
  const search = new URLSearchParams()
  if (params.category) search.set("category", params.category)
  if (params.query) search.set("q", params.query)
  if (params.page && params.page > 1) search.set("page", String(params.page))
  const qs = search.toString()
  return qs ? `/?${qs}` : "/"
}

export default function BoardPage({ searchParams }: PageProps<"/">) {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">게시판</h1>
        <p className="text-sm text-muted-foreground">
          자유롭게 이야기를 나눠 보세요.
        </p>
      </div>
      <Suspense fallback={<BoardSkeleton />}>
        <Board searchParams={searchParams} />
      </Suspense>
    </div>
  )
}

async function Board({
  searchParams,
}: {
  searchParams: PageProps<"/">["searchParams"]
}) {
  const { category, query, page } = parseParams(await searchParams)
  const result = await listPosts({ category, query, page })
  const now = new Date()

  return (
    <>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <nav className="flex flex-wrap gap-1" aria-label="분류">
          <CategoryTab href={boardHref({ query })} active={!category}>
            전체
          </CategoryTab>
          {(Object.keys(CATEGORIES) as Category[]).map((key) => (
            <CategoryTab
              key={key}
              href={boardHref({ category: key, query })}
              active={category === key}
            >
              {CATEGORIES[key]}
            </CategoryTab>
          ))}
        </nav>
        <Form action="/" className="flex gap-2">
          {category && <input type="hidden" name="category" value={category} />}
          <Input
            name="q"
            defaultValue={query}
            placeholder="제목, 내용, 작성자 검색"
            className="sm:w-56"
            aria-label="검색어"
          />
          <Button type="submit" variant="outline" size="icon" aria-label="검색">
            <SearchIcon />
          </Button>
        </Form>
      </div>

      <Card className="py-0">
        <CardContent className="px-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="hidden w-16 text-center sm:table-cell">
                  번호
                </TableHead>
                <TableHead className="w-16 text-center">분류</TableHead>
                <TableHead>제목</TableHead>
                <TableHead className="hidden w-28 md:table-cell">작성자</TableHead>
                <TableHead className="w-24 text-center">작성일</TableHead>
                <TableHead className="hidden w-16 text-center sm:table-cell">
                  조회
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {result.posts.length === 0 ? (
                <TableRow>
                  <TableCell
                    colSpan={6}
                    className="h-32 text-center text-muted-foreground"
                  >
                    {query ? "검색 결과가 없습니다." : "아직 작성된 글이 없습니다."}
                  </TableCell>
                </TableRow>
              ) : (
                result.posts.map((post) => (
                  <TableRow
                    key={post.id}
                    className={cn(post.category === "notice" && "bg-muted/40")}
                  >
                    <TableCell className="hidden text-center text-muted-foreground sm:table-cell">
                      {post.id}
                    </TableCell>
                    <TableCell className="text-center">
                      <Badge
                        variant={post.category === "notice" ? "default" : "secondary"}
                      >
                        {CATEGORIES[post.category]}
                      </Badge>
                    </TableCell>
                    <TableCell className="max-w-0 w-full">
                      <Link
                        href={`/posts/${post.id}`}
                        className="flex items-center gap-1.5 hover:underline"
                      >
                        <span className="truncate">{post.title}</span>
                        {post.commentCount > 0 && (
                          <span className="flex shrink-0 items-center gap-0.5 text-xs text-primary/70">
                            <MessageSquareIcon className="size-3" />
                            {post.commentCount}
                          </span>
                        )}
                      </Link>
                    </TableCell>
                    <TableCell className="hidden truncate md:table-cell">
                      {post.author}
                    </TableCell>
                    <TableCell className="text-center text-muted-foreground tabular-nums">
                      {formatShort(post.createdAt, now)}
                    </TableCell>
                    <TableCell className="hidden text-center text-muted-foreground tabular-nums sm:table-cell">
                      {post.views}
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <div className="flex items-center justify-between text-sm text-muted-foreground">
        <span>총 {result.total}개의 글</span>
      </div>

      {result.totalPages > 1 && (
        <BoardPagination
          page={result.page}
          totalPages={result.totalPages}
          hrefFor={(page) => boardHref({ category, query, page })}
        />
      )}
    </>
  )
}

function CategoryTab({
  href,
  active,
  children,
}: {
  href: string
  active: boolean
  children: React.ReactNode
}) {
  return (
    <Button
      size="sm"
      variant={active ? "default" : "ghost"}
      nativeButton={false}
      render={<Link href={href} aria-current={active ? "page" : undefined} />}
    >
      {children}
    </Button>
  )
}

function BoardSkeleton() {
  return (
    <Card className="py-0">
      <CardContent className="flex flex-col gap-3 p-4">
        {Array.from({ length: 6 }, (_, i) => (
          <div key={i} className="h-6 animate-pulse rounded bg-muted" />
        ))}
      </CardContent>
    </Card>
  )
}
