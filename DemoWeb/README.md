# DemoWeb 게시판

Next.js 16 (App Router) + TypeScript + Tailwind CSS v4 + shadcn/ui로 만든 게시판 웹사이트입니다.

## 기능

- 글 목록: 분류(공지/자유/질문) 필터, 제목·내용·작성자 검색, 페이지네이션
- 글 상세: 조회수, 댓글 작성
- 글쓰기 / 수정 / 삭제: 작성 시 입력한 비밀번호로 수정·삭제 (비밀번호는 scrypt 해시로 저장)
- 다크 모드, 모바일 반응형

## 실행

```bash
npm install
npm run dev
```

http://localhost:3000 에서 확인할 수 있습니다.

## 데이터 저장

데이터는 `data/board.json` 파일에 저장되며, 처음 실행할 때 예시 글과 함께 자동으로 만들어집니다.
예시 글의 비밀번호는 `1234`입니다. 초기 상태로 되돌리려면 `data/board.json`을 지우면 됩니다.

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
  lib/board.ts               JSON 파일 기반 데이터 저장소
```
