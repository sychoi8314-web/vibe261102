# DemoWeb 게시판

Next.js 16 (App Router) + TypeScript + Tailwind CSS v4 + shadcn/ui로 만든 게시판 웹사이트입니다.

## 기능

- 글 목록: 분류(공지/자유/질문) 필터, 제목·내용·작성자 검색, 페이지네이션
- 글 상세: 조회수, 댓글 작성
- 글쓰기 / 수정 / 삭제: 작성 시 입력한 비밀번호로 수정·삭제 (비밀번호는 scrypt 해시로 저장)
- 다크 모드, 모바일 반응형

## 실행

1. `.env.example`을 `.env.local`로 복사하고 `DATABASE_URL`에 Neon PostgreSQL 연결 문자열을 넣습니다.
2. 의존성 설치, 테이블 생성(+예시 글), 개발 서버 실행:

```bash
npm install
npm run db:setup
npm run dev
```

http://localhost:3000 에서 확인할 수 있습니다.

## 데이터 저장

데이터는 [Neon](https://neon.tech) PostgreSQL에 저장됩니다 (`@neondatabase/serverless` 드라이버).
테이블 정의는 `db/schema.sql`에 있고, `npm run db:setup`은 테이블을 만들고 게시판이 비어 있으면 예시 글을 넣습니다.
예시 글의 비밀번호는 `1234`입니다.

## 구조

```
src/
  app/
    page.tsx                 글 목록
    posts/new/page.tsx       글쓰기
    posts/[id]/page.tsx      글 상세 + 댓글
    posts/[id]/edit/page.tsx 글 수정
    actions.ts               Server Actions (작성/수정/삭제/댓글/조회수)
  components/                게시판 컴포넌트, components/ui 는 shadcn/ui
  lib/board.ts               PostgreSQL(Neon) 데이터 접근
db/schema.sql                테이블 정의
scripts/db-setup.mjs         테이블 생성 + 예시 데이터
```
