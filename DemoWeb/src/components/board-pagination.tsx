import {
  Pagination,
  PaginationContent,
  PaginationEllipsis,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from "@/components/ui/pagination"

/** Page numbers to show: first, last, and a window around the current page. */
function pageList(page: number, totalPages: number) {
  const pages: Array<number | "ellipsis"> = []
  for (let p = 1; p <= totalPages; p++) {
    if (p === 1 || p === totalPages || Math.abs(p - page) <= 2) pages.push(p)
    else if (pages.at(-1) !== "ellipsis") pages.push("ellipsis")
  }
  return pages
}

export function BoardPagination({
  page,
  totalPages,
  hrefFor,
}: {
  page: number
  totalPages: number
  hrefFor: (page: number) => string
}) {
  return (
    <Pagination>
      <PaginationContent>
        {page > 1 && (
          <PaginationItem>
            <PaginationPrevious href={hrefFor(page - 1)} text="이전" />
          </PaginationItem>
        )}
        {pageList(page, totalPages).map((p, i) =>
          p === "ellipsis" ? (
            <PaginationItem key={`e${i}`}>
              <PaginationEllipsis />
            </PaginationItem>
          ) : (
            <PaginationItem key={p}>
              <PaginationLink href={hrefFor(p)} isActive={p === page}>
                {p}
              </PaginationLink>
            </PaginationItem>
          )
        )}
        {page < totalPages && (
          <PaginationItem>
            <PaginationNext href={hrefFor(page + 1)} text="다음" />
          </PaginationItem>
        )}
      </PaginationContent>
    </Pagination>
  )
}
